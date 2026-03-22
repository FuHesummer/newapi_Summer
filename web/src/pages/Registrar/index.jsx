import React, { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Typography,
  Banner,
  Table,
  Tag,
  Space,
  Spin,
  Modal,
  InputNumber,
  Select,
  Descriptions,
  Collapse,
  Empty,
  TextArea,
  Input,
  Switch,
} from '@douyinfe/semi-ui';
import { IconRefresh, IconUpload, IconSetting } from '@douyinfe/semi-icons';
import { API, showError, showSuccess, showWarning } from '../../helpers';
import { useTranslation } from 'react-i18next';

const { Text, Title } = Typography;

const PROVIDER_CONFIG = {
  exa: { type: 58, label: 'Exa Search', color: 'blue' },
  tavily: { type: 59, label: 'Tavily Search', color: 'green' },
  augment: { type: 60, label: 'Augment Code', color: 'purple' },
};

function KeyPoolCard({ provider, pool, t, showWaterline }) {
  const config = PROVIDER_CONFIG[provider];
  if (!config) return null;

  const channelCount = pool?.channel_count || 0;

  return (
    <Card
      style={{ marginBottom: 16 }}
      title={
        <Space>
          <Tag color={config.color} size='large'>
            {config.label}
          </Tag>
          <Tag size='large'>
            {t('可用 Key')}: {pool?.active_keys || 0}
          </Tag>
          {showWaterline && pool?.min_keys > 0 && (
            <Text type='tertiary'>
              / {t('水位线')}: {pool.min_keys}
            </Text>
          )}
          {pool?.below_waterline && (
            <Tag color='red' size='small'>
              {t('低于水位线')}
            </Tag>
          )}
        </Space>
      }
    >
      {channelCount === 0 ? (
        <Empty
          description={t('暂无渠道')}
          style={{ padding: '20px 0' }}
        />
      ) : (
        <Collapse>
          {(pool?.channels || []).map((ch) => (
            <Collapse.Panel
              key={ch.channel_id}
              header={
                <Space>
                  <Text strong>{ch.channel_name || `Channel #${ch.channel_id}`}</Text>
                  <Tag color={ch.status === 1 ? 'green' : 'red'} size='small'>
                    {ch.status === 1 ? t('启用') : t('禁用')}
                  </Tag>
                  <Tag>{ch.key_count} keys</Tag>
                </Space>
              }
              itemKey={String(ch.channel_id)}
            >
              {ch.keys && ch.keys.length > 0 ? (
                <Table
                  dataSource={ch.keys.map((k, i) => ({ key: i, key_val: k }))}
                  pagination={false}
                  size='small'
                  bordered
                  columns={[
                    {
                      title: '#',
                      width: 50,
                      render: (_, __, idx) => idx + 1,
                    },
                    {
                      title: 'Key',
                      render: (_, record) => (
                        <Text code style={{ fontSize: 12 }}>
                          {record.key_val}
                        </Text>
                      ),
                    },
                  ]}
                />
              ) : (
                <Text type='tertiary'>{t('暂无 Key')}</Text>
              )}
            </Collapse.Panel>
          ))}
        </Collapse>
      )}
    </Card>
  );
}

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

  // 注册机设置
  const [showSettings, setShowSettings] = useState(false);
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settings, setSettings] = useState({
    enabled: false,
    sidecar_url: 'http://registrar:8081',
    tavily_min_keys: 5,
    check_interval_min: 30,
    registration_proxy: '',
    auto_replenish: false,
  });

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

    // 加载注册机设置
    try {
      const res = await API.get('/api/option/');
      if (res.data.success && Array.isArray(res.data.data)) {
        const optMap = {};
        res.data.data.forEach((opt) => {
          optMap[opt.key] = opt.value;
        });
        setSettings((prev) => ({
          enabled: optMap['registrar_setting.enabled'] === 'true',
          sidecar_url: optMap['registrar_setting.sidecar_url'] || prev.sidecar_url,
          tavily_min_keys: parseInt(optMap['registrar_setting.tavily_min_keys']) || prev.tavily_min_keys,
          check_interval_min: parseInt(optMap['registrar_setting.check_interval_min']) || prev.check_interval_min,
          registration_proxy: optMap['registrar_setting.registration_proxy'] || '',
          auto_replenish: optMap['registrar_setting.auto_replenish'] === 'true',
        }));
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

  const handleSaveSettings = async () => {
    setSettingsLoading(true);
    try {
      const fields = {
        'registrar_setting.enabled': String(settings.enabled),
        'registrar_setting.sidecar_url': settings.sidecar_url,
        'registrar_setting.tavily_min_keys': String(settings.tavily_min_keys),
        'registrar_setting.check_interval_min': String(settings.check_interval_min),
        'registrar_setting.registration_proxy': settings.registration_proxy,
        'registrar_setting.auto_replenish': String(settings.auto_replenish),
      };
      const requests = Object.entries(fields).map(([key, value]) =>
        API.put('/api/option/', { key, value })
      );
      await Promise.all(requests);
      showSuccess(t('保存成功'));
      setShowSettings(false);
      loadStatus();
    } catch (e) {
      showError(t('保存失败'));
    }
    setSettingsLoading(false);
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

  const totalKeys =
    (status?.exa?.active_keys || 0) +
    (status?.tavily?.active_keys || 0) +
    (status?.augment?.active_keys || 0);

  return (
    <Spin spinning={loading}>
      <div style={{ padding: '20px', maxWidth: 960 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 20,
          }}
        >
          <Title heading={4} style={{ margin: 0 }}>
            {t('注册机管理')}
          </Title>
          <Space>
            <Button
              icon={<IconSetting />}
              onClick={() => setShowSettings(true)}
            >
              {t('注册机设置')}
            </Button>
            <Button
              icon={<IconUpload />}
              onClick={() => setShowImport(true)}
            >
              {t('导入 Key')}
            </Button>
            <Button
              icon={<IconRefresh />}
              onClick={loadStatus}
            >
              {t('刷新')}
            </Button>
          </Space>
        </div>

        {/* 总览 */}
        {status && (
          <Card style={{ marginBottom: 20 }}>
            <Descriptions
              row
              size='small'
              data={[
                {
                  key: t('总 Key 数'),
                  value: <Tag size='large' color='blue'>{totalKeys}</Tag>,
                },
                {
                  key: 'Exa',
                  value: <Tag color='blue'>{status.exa?.active_keys || 0}</Tag>,
                },
                {
                  key: 'Tavily',
                  value: (
                    <Space>
                      <Tag color={status.tavily?.below_waterline ? 'red' : 'green'}>
                        {status.tavily?.active_keys || 0}
                      </Tag>
                      <Text type='tertiary' size='small'>
                        / {t('水位线')}: {status.tavily?.min_keys || 5}
                      </Text>
                    </Space>
                  ),
                },
                {
                  key: 'Augment',
                  value: <Tag color='purple'>{status.augment?.active_keys || 0}</Tag>,
                },
                {
                  key: t('注册机状态'),
                  value: status.enabled ? (
                    <Tag color='green'>{t('已启用')}</Tag>
                  ) : (
                    <Tag color='grey'>{t('未启用')}</Tag>
                  ),
                },
              ]}
            />
          </Card>
        )}

        {/* Tavily 注册操作 */}
        <Card
          style={{ marginBottom: 20 }}
          title={t('手动注册 Tavily')}
        >
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
              disabled={!status?.enabled}
            >
              {t('手动注册 Tavily')}
            </Button>
            {status && !status.enabled && (
              <Text type='warning'>
                {t('注册机未启用，请在系统设置中开启')}
              </Text>
            )}
          </Space>
          <div style={{ marginTop: 8 }}>
            <Text type='tertiary' size='small'>
              {t('Exa 和 Augment 只能手动注册后在此导入 Key。Tavily 支持自动注册。')}
            </Text>
          </div>
        </Card>

        {/* 三种渠道 Key 池 */}
        <KeyPoolCard
          provider='tavily'
          pool={status?.tavily}
          t={t}
          showWaterline
        />
        <KeyPoolCard
          provider='exa'
          pool={status?.exa}
          t={t}
        />
        <KeyPoolCard
          provider='augment'
          pool={status?.augment}
          t={t}
        />

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

        {/* 注册机设置弹窗 */}
        <Modal
          title={t('注册机设置')}
          visible={showSettings}
          onOk={handleSaveSettings}
          onCancel={() => setShowSettings(false)}
          confirmLoading={settingsLoading}
          maskClosable={false}
          centered
          okText={t('保存')}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <Text strong>{t('启用注册机')}</Text>
                <br />
                <Text type='tertiary' size='small'>{t('开启后可使用自动注册和手动触发注册功能')}</Text>
              </div>
              <Switch
                checked={settings.enabled}
                onChange={(v) => setSettings({ ...settings, enabled: v })}
              />
            </div>

            <div>
              <Text strong>Sidecar URL</Text>
              <Input
                value={settings.sidecar_url}
                onChange={(v) => setSettings({ ...settings, sidecar_url: v })}
                placeholder='http://registrar:8081'
                style={{ marginTop: 4 }}
              />
              <Text type='tertiary' size='small'>{t('注册机 Sidecar 容器的内部地址')}</Text>
            </div>

            <div>
              <Text strong>{t('Tavily 水位线')}</Text>
              <InputNumber
                value={settings.tavily_min_keys}
                onChange={(v) => setSettings({ ...settings, tavily_min_keys: v })}
                min={0}
                max={100}
                style={{ width: '100%', marginTop: 4 }}
              />
              <Text type='tertiary' size='small'>{t('Tavily Key 数量低于此值时触发告警')}</Text>
            </div>

            <div>
              <Text strong>{t('检查间隔（分钟）')}</Text>
              <InputNumber
                value={settings.check_interval_min}
                onChange={(v) => setSettings({ ...settings, check_interval_min: v })}
                min={1}
                max={1440}
                style={{ width: '100%', marginTop: 4 }}
              />
            </div>

            <div>
              <Text strong>{t('注册代理')}</Text>
              <Input
                value={settings.registration_proxy}
                onChange={(v) => setSettings({ ...settings, registration_proxy: v })}
                placeholder='socks5://127.0.0.1:1080'
                style={{ marginTop: 4 }}
              />
              <Text type='tertiary' size='small'>{t('仅 Playwright 浏览器注册走代理，邮箱 API 直连')}</Text>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <Text strong>{t('自动补号')}</Text>
                <br />
                <Text type='tertiary' size='small'>{t('低于水位线时自动注册新账号')}</Text>
              </div>
              <Switch
                checked={settings.auto_replenish}
                onChange={(v) => setSettings({ ...settings, auto_replenish: v })}
              />
            </div>
          </div>
        </Modal>

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
            <TextArea
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
