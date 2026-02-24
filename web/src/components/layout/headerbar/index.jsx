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
import { useHeaderBar } from '../../../hooks/common/useHeaderBar';
import { useNotifications } from '../../../hooks/common/useNotifications';
import { useNavigation } from '../../../hooks/common/useNavigation';
import NoticeModal from '../NoticeModal';
import MobileMenuButton from './MobileMenuButton';
import HeaderLogo from './HeaderLogo';
import Navigation from './Navigation';
import ActionButtons from './ActionButtons';

const HeaderBar = ({ onMobileMenuToggle, drawerOpen }) => {
  const {
    userState,
    statusState,
    isMobile,
    collapsed,
    logoLoaded,
    currentLang,
    isLoading,
    systemName,
    logo,
    isNewYear,
    isSelfUseMode,
    docsLink,
    isDemoSiteMode,
    isConsoleRoute,
    theme,
    headerNavModules,
    pricingRequireAuth,
    logout,
    handleLanguageChange,
    handleThemeToggle,
    handleMobileMenuToggle,
    navigate,
    t,
  } = useHeaderBar({ onMobileMenuToggle, drawerOpen });

  const {
    noticeVisible,
    unreadCount,
    handleNoticeOpen,
    handleNoticeClose,
    getUnreadKeys,
  } = useNotifications(statusState);

  const { mainNavLinks } = useNavigation(t, docsLink, headerNavModules);

  return (
    <header className='sticky top-0 z-50 text-[var(--semi-color-text-0)] transition-colors duration-300'>
      <NoticeModal
        visible={noticeVisible}
        onClose={handleNoticeClose}
        isMobile={isMobile}
        defaultTab={unreadCount > 0 ? 'system' : 'inApp'}
        unreadKeys={getUnreadKeys()}
      />

      <div className='w-full h-16 px-2 sm:px-3'>
        <div className='mx-auto h-full w-full max-w-[1320px] flex items-center'>
          <div className='relative grid h-[52px] w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 rounded-2xl border border-[var(--glass-border)] bg-[color-mix(in_srgb,var(--glass-bg)_90%,transparent)] px-2 sm:px-3 shadow-[var(--glass-shadow)] backdrop-blur-[14px]'>
            <div className='flex items-center'>
              <MobileMenuButton
                isConsoleRoute={isConsoleRoute}
                isMobile={isMobile}
                drawerOpen={drawerOpen}
                collapsed={collapsed}
                onToggle={handleMobileMenuToggle}
                t={t}
              />

              <HeaderLogo
                isMobile={isMobile}
                isConsoleRoute={isConsoleRoute}
                logo={logo}
                logoLoaded={logoLoaded}
                isLoading={isLoading}
                systemName={systemName}
                isSelfUseMode={isSelfUseMode}
                isDemoSiteMode={isDemoSiteMode}
                t={t}
              />
            </div>

            <Navigation
              mainNavLinks={mainNavLinks}
              isMobile={isMobile}
              isLoading={isLoading}
              userState={userState}
              pricingRequireAuth={pricingRequireAuth}
            />

            <ActionButtons
              isNewYear={isNewYear}
              unreadCount={unreadCount}
              onNoticeOpen={handleNoticeOpen}
              theme={theme}
              onThemeToggle={handleThemeToggle}
              currentLang={currentLang}
              onLanguageChange={handleLanguageChange}
              userState={userState}
              isLoading={isLoading}
              isMobile={isMobile}
              isSelfUseMode={isSelfUseMode}
              logout={logout}
              navigate={navigate}
              t={t}
            />

            <div className='pointer-events-none absolute inset-x-4 bottom-0 h-px bg-gradient-to-r from-transparent via-[var(--glass-border)] to-transparent' />
          </div>
        </div>
      </div>
    </header>
  );
};

export default HeaderBar;
