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
