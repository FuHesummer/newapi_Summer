package controller

import (
	"fmt"
	"net/http"
	"strings"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/pkg/registrar"
	"github.com/QuantumNous/new-api/setting"
	"github.com/gin-gonic/gin"
)

// TriggerRegistration 手动触发注册
func TriggerRegistration(c *gin.Context) {
	if !setting.IsRegistrarEnabled() {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "注册机未启用"})
		return
	}

	var req struct {
		Provider string `json:"provider"` // "tavily" or "exa"
		Count    int    `json:"count"`
		Proxy    string `json:"proxy"`
		Accounts string `json:"accounts"` // Tavily Google 账号批量导入（email|password|recovery|2fa|region 格式，多行）
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		common.ApiErrorMsg(c, "参数错误")
		return
	}
	if req.Count <= 0 {
		req.Count = 1
	}
	if req.Count > 10 {
		req.Count = 10
	}

	cfg := setting.GetRegistrarSetting()
	proxy := req.Proxy
	if proxy == "" {
		proxy = cfg.RegistrationProxy
	}

	client := registrar.NewClient(cfg.SidecarURL)

	switch req.Provider {
	case "tavily":
		var result *registrar.RegisterResponse
		var err error

		if req.Accounts != "" {
			// 使用 Google 账号批量注册模式
			result, err = client.RegisterTavilyWithAccounts(req.Accounts, proxy)
		} else {
			// 旧模式：自动注册（需要 sidecar 已有账号池）
			result, err = client.RegisterTavily(req.Count, proxy)
		}
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
			return
		}

		// 将成功的 Key 自动写入 Tavily Channel
		importedCount := 0
		for _, key := range result.Keys {
			if key.APIKey != "" {
				if err := appendKeyToChannel(59, key.APIKey); err != nil { // 59 = ChannelTypeTavily
					common.SysLog(fmt.Sprintf("Failed to import key %s: %s", key.APIKey[:10], err.Error()))
				} else {
					importedCount++
				}
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"success":       true,
			"message":       fmt.Sprintf("注册 %d 个，成功 %d 个，已导入 %d 个 Key", result.Total, result.Successful, importedCount),
			"data":          result,
			"imported_count": importedCount,
		})
	case "exa":
		result, err := client.RegisterExa(req.Count, proxy)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
			return
		}

		// 将成功的 Key 自动写入 Exa Channel
		importedCount := 0
		for _, key := range result.Keys {
			if key.APIKey != "" {
				if err := appendKeyToChannel(58, key.APIKey); err != nil { // 58 = ChannelTypeExa
					common.SysLog(fmt.Sprintf("Failed to import key %s: %s", key.APIKey[:10], err.Error()))
				} else {
					importedCount++
				}
			}
		}

		c.JSON(http.StatusOK, gin.H{
			"success":       true,
			"message":       fmt.Sprintf("注册 %d 个，成功 %d 个，已导入 %d 个 Key", result.Total, result.Successful, importedCount),
			"data":          result,
			"imported_count": importedCount,
		})
	default:
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "不支持的 provider: " + req.Provider})
	}
}

// channelKeyPool 某个渠道的 Key 池信息
type channelKeyPool struct {
	ChannelID   int      `json:"channel_id"`
	ChannelName string   `json:"channel_name"`
	KeyCount    int      `json:"key_count"`
	Keys        []string `json:"keys"` // 脱敏后的 key 列表
	Status      int      `json:"status"`
}

// providerKeyPool 某类型的全部 Key 池汇总
type providerKeyPool struct {
	ActiveKeys     int              `json:"active_keys"`
	ChannelCount   int              `json:"channel_count"`
	Channels       []channelKeyPool `json:"channels"`
	MinKeys        int              `json:"min_keys,omitempty"`
	BelowWaterline bool             `json:"below_waterline,omitempty"`
}

// maskKey 对 API Key 脱敏显示，保留前6后4
func maskKey(key string) string {
	key = strings.TrimSpace(key)
	if len(key) <= 10 {
		return key[:1] + "***" + key[len(key)-1:]
	}
	return key[:6] + "***" + key[len(key)-4:]
}

// buildProviderPool 构建某类型渠道的 Key 池汇总
func buildProviderPool(channelType int) providerKeyPool {
	channels, err := model.GetChannelsByType(0, 100, false, channelType)
	if err != nil {
		return providerKeyPool{}
	}

	pool := providerKeyPool{
		ChannelCount: len(channels),
		Channels:     make([]channelKeyPool, 0, len(channels)),
	}

	for _, ch := range channels {
		fullCh, err := model.GetChannelById(ch.Id, true)
		if err != nil {
			continue
		}

		var keys []string
		var maskedKeys []string
		if fullCh.Key != "" {
			raw := strings.Split(fullCh.Key, "\n")
			for _, k := range raw {
				k = strings.TrimSpace(k)
				if k != "" {
					keys = append(keys, k)
					maskedKeys = append(maskedKeys, maskKey(k))
				}
			}
		}

		pool.ActiveKeys += len(keys)
		pool.Channels = append(pool.Channels, channelKeyPool{
			ChannelID:   ch.Id,
			ChannelName: ch.Name,
			KeyCount:    len(keys),
			Keys:        maskedKeys,
			Status:      ch.Status,
		})
	}

	return pool
}

// GetRegistrarStatus 获取水位线状态
func GetRegistrarStatus(c *gin.Context) {
	cfg := setting.GetRegistrarSetting()

	tavilyPool := buildProviderPool(59)
	tavilyPool.MinKeys = cfg.TavilyMinKeys
	tavilyPool.BelowWaterline = tavilyPool.ActiveKeys < cfg.TavilyMinKeys

	exaPool := buildProviderPool(58)
	exaPool.MinKeys = cfg.ExaMinKeys
	exaPool.BelowWaterline = exaPool.ActiveKeys < cfg.ExaMinKeys

	augmentPool := buildProviderPool(60)

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"data": gin.H{
			"enabled":        cfg.Enabled,
			"sidecar_url":    cfg.SidecarURL,
			"auto_replenish": cfg.AutoReplenish,
			"tavily":         tavilyPool,
			"exa":            exaPool,
			"augment":        augmentPool,
		},
	})
}

// ImportKeys 批量导入 Key
func ImportKeys(c *gin.Context) {
	var req struct {
		ChannelType int    `json:"channel_type"` // 58=Exa, 59=Tavily, 60=Augment
		Keys        string `json:"keys"`         // 一行一个
	}
	if err := c.ShouldBindJSON(&req); err != nil {
		common.ApiErrorMsg(c, "参数错误")
		return
	}

	keys := strings.Split(strings.TrimSpace(req.Keys), "\n")
	imported := 0
	for _, key := range keys {
		key = strings.TrimSpace(key)
		if key == "" {
			continue
		}
		if err := appendKeyToChannel(req.ChannelType, key); err != nil {
			common.SysLog(fmt.Sprintf("Failed to import key: %s", err.Error()))
		} else {
			imported++
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"success": true,
		"message": fmt.Sprintf("成功导入 %d 个 Key", imported),
		"data":    imported,
	})
}

// GetDomainStatus 获取域名熔断状态
func GetDomainStatus(c *gin.Context) {
	if !setting.IsRegistrarEnabled() {
		c.JSON(http.StatusOK, gin.H{"success": true, "data": []interface{}{}})
		return
	}

	cfg := setting.GetRegistrarSetting()
	client := registrar.NewClient(cfg.SidecarURL)

	domains, err := client.GetDomainStatus()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"success": true, "data": domains})
}

// appendKeyToChannel 将 Key 追加到指定类型的第一个 Channel
func appendKeyToChannel(channelType int, key string) error {
	channels, err := model.GetChannelsByType(0, 1, false, channelType)
	if err != nil || len(channels) == 0 {
		return fmt.Errorf("no channel found for type %d", channelType)
	}

	ch := channels[0]
	// 重新查一次带 Key 的完整数据
	fullCh, err := model.GetChannelById(ch.Id, true)
	if err != nil {
		return err
	}

	existingKey := fullCh.Key
	if existingKey == "" {
		existingKey = key
	} else {
		existingKey = existingKey + "\n" + key
	}

	return model.DB.Model(&model.Channel{}).Where("id = ?", ch.Id).Update("key", existingKey).Error
}

