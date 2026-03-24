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

import React, { useState } from 'react';
import { Button, Modal, Input, Typography } from '@douyinfe/semi-ui';
import { API, showError, showSuccess } from '../../../helpers';

const UsersActions = ({ setShowAddUser, groupOptions, refresh, t }) => {
  const [showBatchGroup, setShowBatchGroup] = useState(false);
  const [batchRemark, setBatchRemark] = useState('');
  const [batchGroup, setBatchGroup] = useState('');
  const [batchLoading, setBatchLoading] = useState(false);

  const handleAddUser = () => {
    setShowAddUser(true);
  };

  const handleBatchSetGroup = async () => {
    if (!batchRemark.trim() || !batchGroup.trim()) {
      showError(t('请填写备注和目标分组'));
      return;
    }
    setBatchLoading(true);
    try {
      const res = await API.post('/api/user/batch/group', {
        remark: batchRemark.trim(),
        group: batchGroup.trim(),
      });
      const { success, message } = res.data;
      if (success) {
        showSuccess(message);
        setShowBatchGroup(false);
        setBatchRemark('');
        setBatchGroup('');
        if (refresh) refresh();
      } else {
        showError(message);
      }
    } catch (e) {
      showError(t('操作失败'));
    }
    setBatchLoading(false);
  };

  return (
    <>
      <div className='flex gap-2 w-full md:w-auto order-2 md:order-1'>
        <Button className='w-full md:w-auto' onClick={handleAddUser} size='small'>
          {t('添加用户')}
        </Button>
        <Button
          className='w-full md:w-auto'
          onClick={() => setShowBatchGroup(true)}
          size='small'
          type='tertiary'
        >
          {t('按备注设置分组')}
        </Button>
      </div>

      <Modal
        title={t('按备注批量设置分组')}
        visible={showBatchGroup}
        onOk={handleBatchSetGroup}
        onCancel={() => setShowBatchGroup(false)}
        confirmLoading={batchLoading}
        maskClosable={false}
        centered
        size='small'
      >
        <div style={{ marginBottom: 16 }}>
          <Typography.Text type='tertiary'>
            {t('将所有备注完全匹配的用户统一设置为指定分组')}
          </Typography.Text>
        </div>
        <div style={{ marginBottom: 12 }}>
          <Typography.Text strong>{t('备注关键字')}</Typography.Text>
          <Input
            placeholder={t('输入备注内容（精确匹配）')}
            value={batchRemark}
            onChange={(v) => setBatchRemark(v)}
            style={{ marginTop: 4 }}
          />
        </div>
        <div>
          <Typography.Text strong>{t('目标分组')}</Typography.Text>
          <Input
            placeholder={t('输入目标分组名，如 linuxdo_tl2')}
            value={batchGroup}
            onChange={(v) => setBatchGroup(v)}
            style={{ marginTop: 4 }}
          />
        </div>
      </Modal>
    </>
  );
};

export default UsersActions;
