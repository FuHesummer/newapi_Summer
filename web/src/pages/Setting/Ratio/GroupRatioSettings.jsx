/*
Copyright (C) 2025 QuantumNous

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.

For commercial licensing, please contact support@quantumnous.com
*/

import React, { useEffect, useState, useRef } from 'react';
import {
  Button,
  Col,
  Form,
  Row,
  Spin,
  Banner,
  Table,
  InputNumber,
  Space,
  Typography,
} from '@douyinfe/semi-ui';
import { IconPlus, IconDelete } from '@douyinfe/semi-icons';
import {
  compareObjects,
  API,
  showError,
  showSuccess,
  showWarning,
  verifyJSON,
  toBoolean,
} from '../../../helpers';
import { useTranslation } from 'react-i18next';

export default function GroupRatioSettings(props) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [inputs, setInputs] = useState({
    GroupRatio: '',
    UserUsableGroups: '',
    GroupGroupRatio: '',
    'group_ratio_setting.group_special_usable_group': '',
    AutoGroups: '',
    DefaultUseAutoGroup: false,
  });
  const refForm = useRef();
  const [inputsRow, setInputsRow] = useState(inputs);

  // LinuxDO 模式检测
  const [linuxDOMode, setLinuxDOMode] = useState(false);

  // 可视化编辑的分组倍率数据
  const [groupRatioData, setGroupRatioData] = useState({});
  const [newGroupName, setNewGroupName] = useState('');

  useEffect(() => {
    // 检测是否启用了 LinuxDO 分组锁定
    const enabled = props.options?.['linuxdo_group_mapping.enabled'];
    const lockGroup = props.options?.['linuxdo_group_mapping.lock_group'];
    setLinuxDOMode(toBoolean(enabled) && toBoolean(lockGroup));
  }, [props.options]);

  async function onSubmit() {
    try {
      // 如果是 LinuxDO 模式，同步可视化数据回 JSON
      let finalInputs = { ...inputs };
      if (linuxDOMode) {
        finalInputs.GroupRatio = JSON.stringify(groupRatioData, null, 2);
      }

      await refForm.current
        .validate()
        .then(() => {
          const updateArray = compareObjects(finalInputs, inputsRow);
          if (!updateArray.length)
            return showWarning(t('你似乎并没有修改什么'));

          const requestQueue = updateArray.map((item) => {
            const value =
              typeof finalInputs[item.key] === 'boolean'
                ? String(finalInputs[item.key])
                : finalInputs[item.key];
            return API.put('/api/option/', { key: item.key, value });
          });

          setLoading(true);
          Promise.all(requestQueue)
            .then((res) => {
              if (res.includes(undefined)) {
                return showError(
                  requestQueue.length > 1
                    ? t('部分保存失败，请重试')
                    : t('保存失败'),
                );
              }

              for (let i = 0; i < res.length; i++) {
                if (!res[i].data.success) {
                  return showError(res[i].data.message);
                }
              }

              showSuccess(t('保存成功'));
              props.refresh();
            })
            .catch((error) => {
              console.error('Unexpected error:', error);
              showError(t('保存失败，请重试'));
            })
            .finally(() => {
              setLoading(false);
            });
        })
        .catch(() => {
          showError(t('请检查输入'));
        });
    } catch (error) {
      showError(t('请检查输入'));
      console.error(error);
    }
  }

  useEffect(() => {
    const currentInputs = {};
    for (let key in props.options) {
      if (Object.keys(inputs).includes(key)) {
        currentInputs[key] = props.options[key];
      }
    }
    setInputs(currentInputs);
    setInputsRow(structuredClone(currentInputs));
    refForm.current.setValues(currentInputs);

    // 解析分组倍率为可视化数据
    try {
      if (currentInputs.GroupRatio) {
        const parsed = JSON.parse(currentInputs.GroupRatio);
        setGroupRatioData(parsed);
      }
    } catch (e) {
      // ignore
    }
  }, [props.options]);

  // 可视化编辑器操作
  const handleRatioChange = (group, value) => {
    setGroupRatioData((prev) => ({ ...prev, [group]: value }));
    // 同步回 JSON
    const updated = { ...groupRatioData, [group]: value };
    setInputs((prev) => ({
      ...prev,
      GroupRatio: JSON.stringify(updated, null, 2),
    }));
  };

  const handleDeleteGroup = (group) => {
    setGroupRatioData((prev) => {
      const next = { ...prev };
      delete next[group];
      setInputs((p) => ({
        ...p,
        GroupRatio: JSON.stringify(next, null, 2),
      }));
      return next;
    });
  };

  const handleAddGroup = () => {
    const name = newGroupName.trim();
    if (!name) {
      showWarning(t('请输入分组名称'));
      return;
    }
    if (groupRatioData[name] !== undefined) {
      showWarning(t('该分组已存在'));
      return;
    }
    const updated = { ...groupRatioData, [name]: 1 };
    setGroupRatioData(updated);
    setInputs((prev) => ({
      ...prev,
      GroupRatio: JSON.stringify(updated, null, 2),
    }));
    setNewGroupName('');
  };

  // 可视化表格列
  const ratioColumns = [
    {
      title: t('分组名称'),
      dataIndex: 'group',
      key: 'group',
      width: 200,
    },
    {
      title: t('倍率'),
      dataIndex: 'ratio',
      key: 'ratio',
      width: 200,
      render: (text, record) => (
        <InputNumber
          value={record.ratio}
          min={0}
          step={0.1}
          onChange={(value) => handleRatioChange(record.group, value)}
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: t('说明'),
      key: 'desc',
      render: (text, record) => (
        <Typography.Text type='tertiary' size='small'>
          {record.ratio === 1
            ? t('原价')
            : record.ratio < 1
              ? t('{{percent}}% 折扣', {
                  percent: Math.round((1 - record.ratio) * 100),
                })
              : t('{{percent}}% 加价', {
                  percent: Math.round((record.ratio - 1) * 100),
                })}
        </Typography.Text>
      ),
    },
    {
      title: '',
      key: 'action',
      width: 60,
      render: (text, record) => (
        <Button
          icon={<IconDelete />}
          type='danger'
          theme='borderless'
          size='small'
          onClick={() => handleDeleteGroup(record.group)}
        />
      ),
    },
  ];

  const ratioTableData = Object.entries(groupRatioData).map(
    ([group, ratio]) => ({
      key: group,
      group,
      ratio,
    }),
  );

  // LinuxDO 简化模式
  if (linuxDOMode) {
    return (
      <Spin spinning={loading}>
        <Form
          values={inputs}
          getFormApi={(formAPI) => (refForm.current = formAPI)}
          style={{ marginBottom: 15 }}
        >
          <Banner
            type='info'
            description={t(
              '当前已启用 LinuxDO 等级分组锁定模式，用户分组由系统自动管理。此处只需设置每个等级分组的价格倍率。',
            )}
            style={{ marginBottom: 16 }}
          />

          <Form.Section text={t('分组倍率设置')}>
            <Typography.Text
              type='tertiary'
              style={{ marginBottom: 12, display: 'block' }}
            >
              {t(
                '倍率 1 = 原价，0.5 = 五折，0 = 免费。数值越小用户使用模型越便宜。',
              )}
            </Typography.Text>

            {ratioTableData.length > 0 && (
              <Table
                columns={ratioColumns}
                dataSource={ratioTableData}
                pagination={false}
                size='small'
                style={{ marginBottom: 16 }}
              />
            )}

            <Space style={{ marginBottom: 16 }}>
              <Form.Input
                field='_new_ratio_group'
                label=''
                noLabel
                placeholder={t('输入分组名称，如 linuxdo_tl0')}
                value={newGroupName}
                onChange={(value) => setNewGroupName(value)}
                style={{ width: 250 }}
              />
              <Button icon={<IconPlus />} onClick={handleAddGroup}>
                {t('添加分组')}
              </Button>
            </Space>
          </Form.Section>
        </Form>
        <Button onClick={onSubmit}>{t('保存分组倍率设置')}</Button>
      </Spin>
    );
  }

  // 原始高级模式
  return (
    <Spin spinning={loading}>
      <Form
        values={inputs}
        getFormApi={(formAPI) => (refForm.current = formAPI)}
        style={{ marginBottom: 15 }}
      >
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('分组倍率')}
              placeholder={t('为一个 JSON 文本，键为分组名称，值为倍率')}
              extraText={t(
                '分组倍率设置，可以在此处新增分组或修改现有分组的倍率，格式为 JSON 字符串，例如：{"vip": 0.5, "test": 1}，表示 vip 分组的倍率为 0.5，test 分组的倍率为 1',
              )}
              field={'GroupRatio'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: t('不是合法的 JSON 字符串'),
                },
              ]}
              onChange={(value) =>
                setInputs({ ...inputs, GroupRatio: value })
              }
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('用户可选分组')}
              placeholder={t('为一个 JSON 文本，键为分组名称，值为分组描述')}
              extraText={t(
                '用户新建令牌时可选的分组，格式为 JSON 字符串，例如：{"vip": "VIP 用户", "test": "测试"}，表示用户可以选择 vip 分组和 test 分组',
              )}
              field={'UserUsableGroups'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: t('不是合法的 JSON 字符串'),
                },
              ]}
              onChange={(value) =>
                setInputs({ ...inputs, UserUsableGroups: value })
              }
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('分组特殊倍率')}
              placeholder={t('为一个 JSON 文本')}
              extraText={t(
                '键为分组名称，值为另一个 JSON 对象，键为分组名称，值为该分组的用户的特殊分组倍率，例如：{"vip": {"default": 0.5, "test": 1}}，表示 vip 分组的用户在使用default分组的令牌时倍率为0.5，使用test分组时倍率为1',
              )}
              field={'GroupGroupRatio'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: t('不是合法的 JSON 字符串'),
                },
              ]}
              onChange={(value) =>
                setInputs({ ...inputs, GroupGroupRatio: value })
              }
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('分组特殊可用分组')}
              placeholder={t('为一个 JSON 文本')}
              extraText={t(
                '键为用户分组名称，值为操作映射对象。内层键以"+:"开头表示添加指定分组（键值为分组名称，值为描述），以"-:"开头表示移除指定分组（键值为分组名称），不带前缀的键直接添加该分组。例如：{"vip": {"+:premium": "高级分组", "special": "特殊分组", "-:default": "默认分组"}}，表示 vip 分组的用户可以使用 premium 和 special 分组，同时移除 default 分组的访问权限',
              )}
              field={'group_ratio_setting.group_special_usable_group'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => verifyJSON(value),
                  message: t('不是合法的 JSON 字符串'),
                },
              ]}
              onChange={(value) =>
                setInputs({
                  ...inputs,
                  'group_ratio_setting.group_special_usable_group': value,
                })
              }
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col xs={24} sm={16}>
            <Form.TextArea
              label={t('自动分组auto，从第一个开始选择')}
              placeholder={t('为一个 JSON 文本')}
              field={'AutoGroups'}
              autosize={{ minRows: 6, maxRows: 12 }}
              trigger='blur'
              stopValidateWithError
              rules={[
                {
                  validator: (rule, value) => {
                    if (!value || value.trim() === '') {
                      return true; // Allow empty values
                    }

                    // First check if it's valid JSON
                    try {
                      const parsed = JSON.parse(value);

                      // Check if it's an array
                      if (!Array.isArray(parsed)) {
                        return false;
                      }

                      // Check if every element is a string
                      return parsed.every((item) => typeof item === 'string');
                    } catch (error) {
                      return false;
                    }
                  },
                  message: t('必须是有效的 JSON 字符串数组，例如：["g1","g2"]'),
                },
              ]}
              onChange={(value) =>
                setInputs({ ...inputs, AutoGroups: value })
              }
            />
          </Col>
        </Row>
        <Row gutter={16}>
          <Col span={16}>
            <Form.Switch
              label={t(
                '创建令牌默认选择auto分组，初始令牌也将设为auto（否则留空，为用户默认分组）',
              )}
              field={'DefaultUseAutoGroup'}
              onChange={(value) =>
                setInputs({ ...inputs, DefaultUseAutoGroup: value })
              }
            />
          </Col>
        </Row>
      </Form>
      <Button onClick={onSubmit}>{t('保存分组倍率设置')}</Button>
    </Spin>
  );
}
