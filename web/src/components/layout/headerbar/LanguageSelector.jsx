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
import { Button, Dropdown } from '@douyinfe/semi-ui';
import { Languages } from 'lucide-react';

const LanguageSelector = ({ currentLang, onLanguageChange, t }) => {
  return (
    <Dropdown
      position='bottomRight'
      render={
        <Dropdown.Menu className='!bg-[color-mix(in_srgb,var(--glass-bg)_92%,transparent)] !border-[var(--glass-border)] !shadow-lg !rounded-lg backdrop-blur-md'>
          {/* Language sorting: Order by English name (Chinese, English, French, Japanese, Russian) */}
          <Dropdown.Item
            onClick={() => onLanguageChange('zh-CN')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'zh-CN' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            简体中文
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('zh-TW')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'zh-TW' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
        	繁體中文
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('en')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'en' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            English
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('fr')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'fr' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            Français
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('ja')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'ja' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            日本語
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('ru')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'ru' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            Русский
          </Dropdown.Item>
          <Dropdown.Item
            onClick={() => onLanguageChange('vi')}
            className={`!px-3 !py-1.5 !text-sm !text-[var(--semi-color-text-0)] ${currentLang === 'vi' ? '!bg-[color-mix(in_srgb,var(--glass-bg)_82%,rgba(59,130,246,0.20))] !font-semibold' : 'hover:!bg-[var(--glass-bg-hover)]'}`}
          >
            Tiếng Việt
          </Dropdown.Item>
        </Dropdown.Menu>
      }
    >
      <Button
        icon={<Languages size={18} />}
        aria-label={t('common.changeLanguage')}
        theme='borderless'
        type='tertiary'
        className='!p-1.5 !text-current !rounded-full !bg-[color-mix(in_srgb,var(--glass-bg)_90%,transparent)] hover:!bg-[var(--glass-bg-hover)] focus:!bg-[var(--glass-bg-hover)]'
      />
    </Dropdown>
  );
};

export default LanguageSelector;
