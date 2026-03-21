import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Typography,
  Banner,
  Table,
  Tag,
  Space,
  Spin,
  Modal,
  InputNumber,
  Select,
} from '@douyinfe/semi-ui';
import { IconRefresh, IconUpload } from '@douyinfe/semi-icons';
import { API, showError, showSuccess, showWarning } from '../../helpers';
import { useTranslation } from 'react-i18next';

const { Text, Title } = Typography;

export default function RegistrarPage() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [domains, setDomains] = useState([]);
  const [showImport, setShowImport] = useState(false);
  const [importType, setImportType] = useState(59);
  const [importKeys, setImportKeys] = useState('');
  const [importLoading, setImportLoading] = useState(false);
  const [registerLoading, setRegisterLoading] = useState(false);
  const [registerCount, setRegisterCount] = useState(1);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const res = await API.get('/api/registrar/status');
      if (res.data.success) {
        setStatus(res.data.data);
      }
    } catch (e) {
      // ignore
    }

    try {
      const res = await API.get('/api/registrar/domains');
      if (res.data.success) {
        setDomains(res.data.data || []);
      }
    } catch (e) {
      // ignore
    }
    setLoading(false);
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleTriggerRegister = async () => {
    setRegisterLoading(true);
    try {
      const res = await API.post('/api/registrar/trigger', {
        provider: 'tavily',
        count: registerCount,
      });
      if (res.data.success) {
        showSuccess(res.data.message);
        loadStatus();
      } else {
        showError(res.data.message);
      }
    } catch (e) {
      showError(t('注册失败'));
    }
    setRegisterLoading(false);
  };

  const handleImport = async () => {
    if (!importKeys.trim()) {
      showWarning(t('请输入 Key'));
      return;
    }
    setImportLoading(true);
    try {
      const res = await API.post('/api/registrar/import', {
        channel_type: importType,
        keys: importKeys.trim(),
      });
      if (res.data.success) {
        showSuccess(res.data.message);
        setShowImport(false);
        setImportKeys('');
        loadStatus();
      } else {
        showError(res.data.message);
      }
    } catch (e) {
      showError(t('导入失败'));
    }
    setImportLoading(false);
  };

  const domainColumns = [
    {
      title: t('域名'),
      dataIndex: 'domain',
      key: 'domain',
    },
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      render: (text) => (
        <Tag color={text === 'healthy' ? 'green' : 'red'} shape='circle'>
          {text === 'healthy' ? t('健康') : t('熔断')}
        </Tag>
      ),
    },
    {
      title: t('成功/失败'),
      key: 'stats',
      render: (_, record) => (
        <Text>
          {record.success} / {record.fail}
        </Text>
      ),
    },
    {
      title: t('剩余冷却'),
      dataIndex: 'remaining_seconds',
      key: 'remaining',
      render: (val) =>
        val > 0 ? (
          <Tag color='orange'>{val}s</Tag>
        ) : (
          <Text type='tertiary'>-</Text>
        ),
    },
  ];

  return (
    <Spin spinning={loading}>
      <div style={{ padding: '20px', maxWidth: 900 }}>
        <Title heading={4} style={{ marginBottom: 20 }}>
          {t('注册机管理')}
        </Title>

        {/* 水位线状态 */}
        <Card
          title={t('Tavily Key 池状态')}
          style={{ marginBottom: 20 }}
          headerExtraContent={
            <Button
              icon={<IconRefresh />}
              size='small'
              onClick={loadStatus}
            >
              {t('刷新')}
            </Button>
          }
        >
          {status ? (
            <div>
              <Space style={{ marginBottom: 16 }}>
                <Text strong>{t('可用 Key')}:</Text>
                <Tag
                  color={
                    status.tavily?.below_waterline ? 'red' : 'green'
                  }
                  size='large'
                >
                  {status.tavily?.active_keys || 0}
                </Tag>
                <Text type='tertiary'>
                  / {t('水位线')}: {status.tavily?.min_keys || 5}
                </Text>
                {status.tavily?.below_waterline && (
                  <Tag color='red'>{t('低于水位线')}</Tag>
                )}
              </Space>

              <div style={{ marginTop: 16 }}>
                <Space>
                  <InputNumber
                    min={1}
                    max={10}
                    value={registerCount}
                    onChange={(v) => setRegisterCount(v)}
                    style={{ width: 80 }}
                  />
                  <Button
                    type='primary'
                    loading={registerLoading}
                    onClick={handleTriggerRegister}
                    disabled={!status.enabled}
                  >
                    {t('手动注册 Tavily')}
                  </Button>
                  {!status.enabled && (
                    <Text type='warning'>
                      {t('注册机未启用，请在系统设置中开启')}
                    </Text>
                  )}
                </Space>
              </div>
            </div>
          ) : (
            <Text type='tertiary'>{t('加载中...')}</Text>
          )}
        </Card>

        {/* 域名熔断状态 */}
        <Card
          title={t('DuckMail 域名熔断状态')}
          style={{ marginBottom: 20 }}
        >
          {domains.length > 0 ? (
            <Table
              columns={domainColumns}
              dataSource={domains.map((d, i) => ({ ...d, key: i }))}
              pagination={false}
              size='small'
            />
          ) : (
            <Banner
              type='info'
              description={t(
                '注册机未启用或 Sidecar 未连接，无法获取域名状态'
              )}
            />
          )}
        </Card>

        {/* 批量导入 Key */}
        <Card title={t('批量导入 Key')}>
          <Banner
            type='info'
            description={t(
              'Exa 和 Augment 只能手动注册后在此导入 Key。Tavily 支持自动注册。'
            )}
            style={{ marginBottom: 16 }}
          />
          <Button
            icon={<IconUpload />}
            onClick={() => setShowImport(true)}
          >
            {t('导入 Key')}
          </Button>
        </Card>

        {/* 导入弹窗 */}
        <Modal
          title={t('批量导入 Key')}
          visible={showImport}
          onOk={handleImport}
          onCancel={() => setShowImport(false)}
          confirmLoading={importLoading}
          maskClosable={false}
          centered
        >
          <div style={{ marginBottom: 12 }}>
            <Text strong>{t('渠道类型')}</Text>
            <Select
              value={importType}
              onChange={(v) => setImportType(v)}
              style={{ width: '100%', marginTop: 4 }}
              optionList={[
                { value: 58, label: 'Exa Search' },
                { value: 59, label: 'Tavily Search' },
                { value: 60, label: 'Augment Code' },
              ]}
            />
          </div>
          <div>
            <Text strong>{t('Key 列表（一行一个）')}</Text>
            <Form.TextArea
              field='_import_keys'
              label=''
              noLabel
              placeholder={t('粘贴 Key，一行一个')}
              value={importKeys}
              onChange={(v) => setImportKeys(v)}
              autosize={{ minRows: 5, maxRows: 10 }}
              style={{ marginTop: 4 }}
            />
          </div>
        </Modal>
      </div>
    </Spin>
  );
}
