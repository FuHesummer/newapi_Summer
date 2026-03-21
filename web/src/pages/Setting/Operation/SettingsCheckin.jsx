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
  Typography,
  Banner,
  Table,
  InputNumber,
  Space,
} from '@douyinfe/semi-ui';
import { IconPlus, IconDelete } from '@douyinfe/semi-icons';
import {
  compareObjects,
  API,
  showError,
  showSuccess,
  showWarning,
} from '../../../helpers';
import { useTranslation } from 'react-i18next';

export default function SettingsCheckin(props) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [inputs, setInputs] = useState({
    'checkin_setting.enabled': false,
    'checkin_setting.min_quota': 1000,
    'checkin_setting.max_quota': 10000,
    'checkin_setting.group_checkin_quotas': '{}',
  });
  const refForm = useRef();
  const [inputsRow, setInputsRow] = useState(inputs);
  const [groupQuotas, setGroupQuotas] = useState({});
  const [newGroupName, setNewGroupName] = useState('');

  function handleFieldChange(fieldName) {
    return (value) => {
      setInputs((inputs) => ({ ...inputs, [fieldName]: value }));
    };
  }

  function onSubmit() {
    // 同步 groupQuotas 回 inputs
    const updatedInputs = {
      ...inputs,
      'checkin_setting.group_checkin_quotas': JSON.stringify(groupQuotas),
    };
    setInputs(updatedInputs);

    const updateArray = compareObjects(updatedInputs, inputsRow);
    if (!updateArray.length) return showWarning(t('你似乎并没有修改什么'));
    const requestQueue = updateArray.map((item) => {
      let value = '';
      if (typeof updatedInputs[item.key] === 'boolean') {
        value = String(updatedInputs[item.key]);
      } else {
        value = String(updatedInputs[item.key]);
      }
      return API.put('/api/option/', {
        key: item.key,
        value,
      });
    });
    setLoading(true);
    Promise.all(requestQueue)
      .then((res) => {
        if (requestQueue.length === 1) {
          if (res.includes(undefined)) return;
        } else if (requestQueue.length > 1) {
          if (res.includes(undefined))
            return showError(t('部分保存失败，请重试'));
        }
        showSuccess(t('保存成功'));
        props.refresh();
      })
      .catch(() => {
        showError(t('保存失败，请重试'));
      })
      .finally(() => {
        setLoading(false);
      });
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
    // 解析分组签到配置
    try {
      const quotas = currentInputs['checkin_setting.group_checkin_quotas'];
      if (quotas && typeof quotas === 'string') {
        setGroupQuotas(JSON.parse(quotas));
      } else if (quotas && typeof quotas === 'object') {
        setGroupQuotas(quotas);
      }
    } catch (e) {
      setGroupQuotas({});
    }
    refForm.current.setValues(currentInputs);
  }, [props.options]);

  const handleAddGroup = () => {
    const name = newGroupName.trim();
    if (!name) {
      showWarning(t('请输入分组名称'));
      return;
    }
    if (groupQuotas[name]) {
      showWarning(t('该分组已存在'));
      return;
    }
    setGroupQuotas((prev) => ({
      ...prev,
      [name]: {
        min_quota: inputs['checkin_setting.min_quota'] || 1000,
        max_quota: inputs['checkin_setting.max_quota'] || 10000,
      },
    }));
    setNewGroupName('');
  };

  const handleDeleteGroup = (groupName) => {
    setGroupQuotas((prev) => {
      const next = { ...prev };
      delete next[groupName];
      return next;
    });
  };

  const handleGroupQuotaChange = (groupName, field, value) => {
    setGroupQuotas((prev) => ({
      ...prev,
      [groupName]: {
        ...prev[groupName],
        [field]: value,
      },
    }));
  };

  const groupQuotaColumns = [
    {
      title: t('分组名称'),
      dataIndex: 'group',
      key: 'group',
      width: 200,
    },
    {
      title: t('签到最小额度'),
      dataIndex: 'min_quota',
      key: 'min_quota',
      width: 200,
      render: (text, record) => (
        <InputNumber
          value={record.min_quota}
          min={0}
          onChange={(value) =>
            handleGroupQuotaChange(record.group, 'min_quota', value)
          }
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: t('签到最大额度'),
      dataIndex: 'max_quota',
      key: 'max_quota',
      width: 200,
      render: (text, record) => (
        <InputNumber
          value={record.max_quota}
          min={0}
          onChange={(value) =>
            handleGroupQuotaChange(record.group, 'max_quota', value)
          }
          style={{ width: '100%' }}
        />
      ),
    },
    {
      title: t('操作'),
      key: 'action',
      width: 80,
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

  const groupQuotaData = Object.entries(groupQuotas).map(([group, quota]) => ({
    key: group,
    group,
    min_quota: quota.min_quota,
    max_quota: quota.max_quota,
  }));

  return (
    <>
      <Spin spinning={loading}>
        <Form
          values={inputs}
          getFormApi={(formAPI) => (refForm.current = formAPI)}
          style={{ marginBottom: 15 }}
        >
          <Form.Section text={t('签到设置')}>
            <Typography.Text
              type='tertiary'
              style={{ marginBottom: 16, display: 'block' }}
            >
              {t('签到功能允许用户每日签到获取随机额度奖励')}
            </Typography.Text>
            <Row gutter={16}>
              <Col xs={24} sm={12} md={8} lg={8} xl={8}>
                <Form.Switch
                  field={'checkin_setting.enabled'}
                  label={t('启用签到功能')}
                  size='default'
                  checkedText='｜'
                  uncheckedText='〇'
                  onChange={handleFieldChange('checkin_setting.enabled')}
                />
              </Col>
              <Col xs={24} sm={12} md={8} lg={8} xl={8}>
                <Form.InputNumber
                  field={'checkin_setting.min_quota'}
                  label={t('签到最小额度') + ` (${t('全局默认')})`}
                  placeholder={t('签到奖励的最小额度')}
                  onChange={handleFieldChange('checkin_setting.min_quota')}
                  min={0}
                  disabled={!inputs['checkin_setting.enabled']}
                />
              </Col>
              <Col xs={24} sm={12} md={8} lg={8} xl={8}>
                <Form.InputNumber
                  field={'checkin_setting.max_quota'}
                  label={t('签到最大额度') + ` (${t('全局默认')})`}
                  placeholder={t('签到奖励的最大额度')}
                  onChange={handleFieldChange('checkin_setting.max_quota')}
                  min={0}
                  disabled={!inputs['checkin_setting.enabled']}
                />
              </Col>
            </Row>
          </Form.Section>

          <Form.Section text={t('分组签到额度')}>
            <Banner
              type='info'
              description={t(
                '为不同用户分组设置独立的签到额度范围，未配置的分组使用全局默认值'
              )}
              style={{ marginBottom: 16 }}
            />
            {groupQuotaData.length > 0 && (
              <Table
                columns={groupQuotaColumns}
                dataSource={groupQuotaData}
                pagination={false}
                size='small'
                style={{ marginBottom: 16 }}
              />
            )}
            <Space style={{ marginBottom: 16 }}>
              <Form.Input
                field='_new_group_name'
                label=''
                noLabel
                placeholder={t('输入分组名称，如 linuxdo_tl0')}
                value={newGroupName}
                onChange={(value) => setNewGroupName(value)}
                style={{ width: 250 }}
              />
              <Button
                icon={<IconPlus />}
                onClick={handleAddGroup}
                disabled={!inputs['checkin_setting.enabled']}
              >
                {t('添加分组配置')}
              </Button>
            </Space>
          </Form.Section>

          <Row>
            <Button size='default' onClick={onSubmit}>
              {t('保存签到设置')}
            </Button>
          </Row>
        </Form>
      </Spin>
    </>
  );
}
