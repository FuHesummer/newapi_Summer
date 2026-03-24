package operation_setting

import "github.com/QuantumNous/new-api/setting/config"

// GroupCheckinQuota 分组签到额度配置
type GroupCheckinQuota struct {
	MinQuota int `json:"min_quota"` // 该分组签到最小额度
	MaxQuota int `json:"max_quota"` // 该分组签到最大额度
}

// CheckinSetting 签到功能配置
type CheckinSetting struct {
	Enabled            bool                         `json:"enabled"`              // 是否启用签到功能
	MinQuota           int                          `json:"min_quota"`            // 签到最小额度奖励（全局默认）
	MaxQuota           int                          `json:"max_quota"`            // 签到最大额度奖励（全局默认）
	GroupCheckinQuotas map[string]GroupCheckinQuota  `json:"group_checkin_quotas"` // 分组级签到额度配置
}

// 默认配置
var checkinSetting = CheckinSetting{
	Enabled:            false, // 默认关闭
	MinQuota:           1000,  // 默认最小额度 1000 (约 0.002 USD)
	MaxQuota:           10000, // 默认最大额度 10000 (约 0.02 USD)
	GroupCheckinQuotas: map[string]GroupCheckinQuota{},
}

func init() {
	// 注册到全局配置管理器
	config.GlobalConfig.Register("checkin_setting", &checkinSetting)
}

// GetCheckinSetting 获取签到配置
func GetCheckinSetting() *CheckinSetting {
	return &checkinSetting
}

// IsCheckinEnabled 是否启用签到功能
func IsCheckinEnabled() bool {
	return checkinSetting.Enabled
}

// GetCheckinQuotaRange 获取签到额度范围（全局默认）
func GetCheckinQuotaRange() (min, max int) {
	return checkinSetting.MinQuota, checkinSetting.MaxQuota
}

// GetCheckinQuotaRangeForGroup 获取指定分组的签到额度范围
// 如果该分组有独立配置且有效（MaxQuota > 0），返回分组配置
// 否则返回全局默认配置
func GetCheckinQuotaRangeForGroup(group string) (min, max int) {
	if groupQuota, ok := checkinSetting.GroupCheckinQuotas[group]; ok {
		if groupQuota.MaxQuota > 0 && groupQuota.MaxQuota >= groupQuota.MinQuota {
			return groupQuota.MinQuota, groupQuota.MaxQuota
		}
	}
	return checkinSetting.MinQuota, checkinSetting.MaxQuota
}
