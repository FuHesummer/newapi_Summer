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

import React from 'react';
import { Button } from '@douyinfe/semi-ui';
import { RefreshCw, Search } from 'lucide-react';

const DashboardHeader = ({
  getGreeting,
  greetingVisible,
  showSearchModal,
  refresh,
  loading,
  t,
}) => {
  const iconButtonStyle = {
    borderRadius: 999,
    border: '1px solid var(--glass-border)',
    background: 'color-mix(in srgb, var(--glass-bg) 88%, transparent)',
    color: 'var(--app-text-primary)',
  };

  return (
    <div
      className='flex items-center justify-between mb-4 px-3 py-2 rounded-xl'
      style={{
        background: 'color-mix(in srgb, var(--glass-bg) 82%, transparent)',
        border: '1px solid var(--glass-border)',
      }}
    >
      <h2
        className='text-2xl font-semibold transition-opacity duration-1000 ease-in-out'
        style={{
          opacity: greetingVisible ? 1 : 0,
          color: 'var(--app-text-primary)',
        }}
      >
        {getGreeting}
      </h2>
      <div className='flex gap-3'>
        <Button
          theme='outline'
          type='tertiary'
          icon={<Search size={16} />}
          onClick={showSearchModal}
          style={iconButtonStyle}
        />
        <Button
          theme='outline'
          type='tertiary'
          icon={<RefreshCw size={16} />}
          onClick={refresh}
          loading={loading}
          style={iconButtonStyle}
        />
      </div>
    </div>
  );
};

export default DashboardHeader;
