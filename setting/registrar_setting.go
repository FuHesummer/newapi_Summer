package setting

import "github.com/QuantumNous/new-api/setting/config"

// RegistrarSetting 注册机配置
type RegistrarSetting struct {
	Enabled           bool   `json:"enabled"`            // 是否启用注册机
	SidecarURL        string `json:"sidecar_url"`        // Python sidecar 地址
	TavilyMinKeys     int    `json:"tavily_min_keys"`    // Tavily 最低水位线
	ExaMinKeys        int    `json:"exa_min_keys"`       // Exa 最低水位线
	CheckIntervalMin  int    `json:"check_interval_min"` // 检查间隔（分钟）
	RegistrationProxy string `json:"registration_proxy"` // 注册用代理
	AutoReplenish     bool   `json:"auto_replenish"`     // 是否自动补号
}

var registrarSetting = RegistrarSetting{
	Enabled:           false,
	SidecarURL:        "http://registrar:8081",
	TavilyMinKeys:     5,
	ExaMinKeys:        5,
	CheckIntervalMin:  30,
	RegistrationProxy: "",
	AutoReplenish:     false,
}

func init() {
	config.GlobalConfig.Register("registrar_setting", &registrarSetting)
}

func GetRegistrarSetting() *RegistrarSetting {
	return &registrarSetting
}

func IsRegistrarEnabled() bool {
	return registrarSetting.Enabled
}

func GetRegistrarSidecarURL() string {
	if registrarSetting.SidecarURL == "" {
		return "http://registrar:8081"
	}
	return registrarSetting.SidecarURL
}
