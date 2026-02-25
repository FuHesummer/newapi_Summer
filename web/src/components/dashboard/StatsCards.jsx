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
import { Card, Avatar, Skeleton, Tag } from '@douyinfe/semi-ui';
import { VChart } from '@visactor/react-vchart';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const groupStyleMap = {
  'bg-blue-50': {
    background: 'linear-gradient(135deg, rgba(244, 114, 166, 0.14), rgba(244, 114, 166, 0.08))',
  },
  'bg-green-50': {
    background: 'linear-gradient(135deg, rgba(196, 161, 249, 0.14), rgba(196, 161, 249, 0.08))',
  },
  'bg-yellow-50': {
    background: 'linear-gradient(135deg, rgba(255, 182, 208, 0.16), rgba(244, 114, 166, 0.10))',
  },
  'bg-indigo-50': {
    background: 'linear-gradient(135deg, rgba(224, 192, 255, 0.16), rgba(196, 161, 249, 0.10))',
  },
};

const StatsCards = ({
  groupedStatsData,
  loading,
  getTrendSpec,
  CARD_PROPS,
  CHART_CONFIG,
}) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  return (
    <div className='mb-4'>
      <div className='grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4'>
        {groupedStatsData.map((group, idx) => (
          <Card
            key={idx}
            {...CARD_PROPS}
            className='border-0 !rounded-2xl w-full'
            title={group.title}
            style={groupStyleMap[group.color]}
          >
            <div className='space-y-4'>
              {group.items.map((item, itemIdx) => (
                <div
                  key={itemIdx}
                  className='flex items-center justify-between cursor-pointer rounded-lg px-2 py-1 transition-colors'
                  style={{
                    background:
                      'color-mix(in srgb, var(--glass-bg) 64%, transparent)',
                  }}
                  onClick={item.onClick}
                >
                  <div className='flex items-center'>
                    <Avatar
                      className='mr-3'
                      size='small'
                      color={item.avatarColor}
                      style={{
                        boxShadow:
                          '0 6px 16px color-mix(in srgb, var(--brand-primary) 35%, transparent)',
                      }}
                    >
                      {item.icon}
                    </Avatar>
                    <div>
                      <div
                        className='text-xs'
                        style={{ color: 'var(--app-text-secondary)' }}
                      >
                        {item.title}
                      </div>
                      <div
                        className='text-lg font-semibold'
                        style={{ color: 'var(--app-text-primary)' }}
                      >
                        <Skeleton
                          loading={loading}
                          active
                          placeholder={
                            <Skeleton.Paragraph
                              active
                              rows={1}
                              style={{
                                width: '65px',
                                height: '24px',
                                marginTop: '4px',
                              }}
                            />
                          }
                        >
                          {item.value}
                        </Skeleton>
                      </div>
                    </div>
                  </div>
                  {item.title === t('当前余额') ? (
                    <Tag
                      color='white'
                      shape='circle'
                      size='large'
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate('/console/topup');
                      }}
                    >
                      {t('充值')}
                    </Tag>
                  ) : (
                    (loading ||
                      (item.trendData && item.trendData.length > 0)) && (
                      <div className='w-24 h-10'>
                        <VChart
                          spec={getTrendSpec(item.trendData, item.trendColor)}
                          option={CHART_CONFIG}
                        />
                      </div>
                    )
                  )}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default StatsCards;
