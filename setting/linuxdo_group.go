package setting

import (
	"strconv"
	"strings"

	"github.com/QuantumNous/new-api/setting/config"
)

// LinuxDOGroupMapping LinuxDO trust_level → Group 自动映射配置
type LinuxDOGroupMapping struct {
	Enabled       bool              `json:"enabled"`         // 是否启用自动分组
	TrustLevelMap map[string]string `json:"trust_level_map"` // trust_level → group 映射，如 {"0":"linuxdo_tl0","1":"linuxdo_tl1",...}
	DefaultGroup  string            `json:"default_group"`   // 未绑定 LinuxDO 的用户默认分组（手动创建/密码注册的用户）
	LockGroup     bool              `json:"lock_group"`      // 是否锁定用户分组（用户不能在令牌中选择其他分组）
}

// 默认配置
var linuxdoGroupMapping = LinuxDOGroupMapping{
	Enabled: false,
	TrustLevelMap: map[string]string{
		"0": "linuxdo_tl0",
		"1": "linuxdo_tl1",
		"2": "linuxdo_tl2",
		"3": "linuxdo_tl3",
		"4": "linuxdo_tl4",
	},
	DefaultGroup: "linuxdo_tl0",
	LockGroup:    true,
}

func init() {
	config.GlobalConfig.Register("linuxdo_group_mapping", &linuxdoGroupMapping)
}

// GetLinuxDOGroupMapping 获取 LinuxDO 分组映射配置
func GetLinuxDOGroupMapping() *LinuxDOGroupMapping {
	return &linuxdoGroupMapping
}

// IsLinuxDOAutoGroupEnabled 是否启用 LinuxDO 等级自动分组
func IsLinuxDOAutoGroupEnabled() bool {
	return linuxdoGroupMapping.Enabled
}

// IsLinuxDOGroupLocked 是否锁定用户分组（不允许用户在令牌中选择其他分组）
func IsLinuxDOGroupLocked() bool {
	return linuxdoGroupMapping.Enabled && linuxdoGroupMapping.LockGroup
}

// GetLinuxDODefaultGroup 获取未绑定 LinuxDO 的用户的默认分组
func GetLinuxDODefaultGroup() string {
	if linuxdoGroupMapping.DefaultGroup == "" {
		return "linuxdo_tl0"
	}
	return linuxdoGroupMapping.DefaultGroup
}

// GetGroupForTrustLevel 根据 trust_level 获取对应的 Group 名称
// 返回对应的 group 名称和是否找到的标志
func GetGroupForTrustLevel(level int) (string, bool) {
	levelStr := strings.TrimSpace(strconv.Itoa(level))
	group, ok := linuxdoGroupMapping.TrustLevelMap[levelStr]
	if !ok || group == "" {
		return "", false
	}
	return group, true
}

// IsLinuxDOAutoGroup 判断给定的 group 是否是 LinuxDO 自动分配的分组
// 检查该 group 是否存在于 TrustLevelMap 的 value 中
func IsLinuxDOAutoGroup(group string) bool {
	for _, g := range linuxdoGroupMapping.TrustLevelMap {
		if g == group {
			return true
		}
	}
	return false
}

// IsLinuxDOManagedGroup 判断 group 是否在 LinuxDO 系统管辖范围内
// 包括：TrustLevelMap 中的分组 + DefaultGroup
func IsLinuxDOManagedGroup(group string) bool {
	if IsLinuxDOAutoGroup(group) {
		return true
	}
	if group == linuxdoGroupMapping.DefaultGroup {
		return true
	}
	return false
}
