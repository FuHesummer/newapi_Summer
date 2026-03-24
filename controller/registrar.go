package controller

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/constant"
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
		Provider string `json:"provider"` // "tavily", "exa", or "ace"
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
	case "ace":
		result, err := client.RegisterAce(req.Count, proxy)
		if err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": err.Error()})
			return
		}

		// 将成功的 Key 自动写入 Augment Channel
		importedCount := 0
		for _, key := range result.Keys {
			if key.APIKey != "" {
				if err := appendKeyToChannel(60, key.APIKey); err != nil { // 60 = ChannelTypeAugment
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
	augmentPool.MinKeys = cfg.AceMinKeys
	augmentPool.BelowWaterline = augmentPool.ActiveKeys < cfg.AceMinKeys

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

// aceSessionData ACE saveSession JSON 格式
type aceSessionData struct {
	AccessToken string `json:"accessToken"`
	TenantURL   string `json:"tenantURL"`
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

	// ACE (type=60) 支持 saveSession JSON 格式批量导入
	// 格式: {"accessToken":"xxx","tenantURL":"https://d16.api.augmentcode.com/", ...}
	// 按 tenantURL 分组，每个 tenant 创建/复用一个渠道
	if req.ChannelType == constant.ChannelTypeAugment {
		imported, total, errMsg := importAceTokens(req.Keys)
		if errMsg != "" {
			c.JSON(http.StatusOK, gin.H{
				"success": imported > 0,
				"message": fmt.Sprintf("导入 %d/%d 个 ACE Token。%s", imported, total, errMsg),
				"data":    imported,
			})
			return
		}
		c.JSON(http.StatusOK, gin.H{
			"success": true,
			"message": fmt.Sprintf("成功导入 %d 个 ACE Token", imported),
			"data":    imported,
		})
		return
	}

	// Exa / Tavily: 普通 key 导入（一行一个）
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

// importAceTokens 解析 ACE saveSession JSON 并按 tenantURL 分组导入
func importAceTokens(keysText string) (imported int, total int, errMsg string) {
	lines := strings.Split(strings.TrimSpace(keysText), "\n")

	// 按 tenantURL 分组
	tenantTokens := make(map[string][]string) // tenantURL → []accessToken
	var parseErrors []string

	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		total++

		var session aceSessionData
		if err := common.UnmarshalJsonStr(line, &session); err != nil {
			// 不是 JSON 格式，当作裸 token 处理
			tenantTokens[""] = append(tenantTokens[""], line)
			continue
		}

		if session.AccessToken == "" {
			parseErrors = append(parseErrors, fmt.Sprintf("line %d: missing accessToken", total))
			continue
		}

		tenantURL := strings.TrimRight(session.TenantURL, "/")
		tenantTokens[tenantURL] = append(tenantTokens[tenantURL], session.AccessToken)
	}

	// 逐 tenant 导入
	for tenantURL, tokens := range tenantTokens {
		for _, token := range tokens {
			var err error
			if tenantURL != "" {
				err = appendKeyToAceChannel(tenantURL, token)
			} else {
				err = appendKeyToChannel(constant.ChannelTypeAugment, token)
			}
			if err != nil {
				common.SysLog(fmt.Sprintf("Failed to import ACE token: %s", err.Error()))
			} else {
				imported++
			}
		}
	}

	if len(parseErrors) > 0 {
		errMsg = strings.Join(parseErrors, "; ")
	}
	return
}

// appendKeyToAceChannel 将 ACE Token 追加到指定 tenantURL 的渠道
// 如果该 tenantURL 的渠道不存在，自动创建
func appendKeyToAceChannel(tenantURL string, token string) error {
	channelType := constant.ChannelTypeAugment

	// 查找已有的 Augment 渠道中 BaseURL 匹配的
	channels, err := model.GetChannelsByType(0, 100, false, channelType)
	if err == nil {
		for _, ch := range channels {
			fullCh, err := model.GetChannelById(ch.Id, true)
			if err != nil {
				continue
			}
			chBaseURL := ""
			if fullCh.BaseURL != nil {
				chBaseURL = strings.TrimRight(*fullCh.BaseURL, "/")
			}
			if chBaseURL == tenantURL {
				// 找到匹配的渠道，追加 key
				existingKey := fullCh.Key
				if existingKey == "" {
					existingKey = token
				} else {
					existingKey = existingKey + "\n" + token
				}
				return model.DB.Model(&model.Channel{}).Where("id = ?", ch.Id).Update("key", existingKey).Error
			}
		}
	}

	// 没找到匹配的渠道，自动创建
	common.SysLog(fmt.Sprintf("No ACE channel found for tenant %s, auto-creating...", tenantURL))
	newCh := &model.Channel{
		Type:        channelType,
		Name:        fmt.Sprintf("Augment (%s)", extractTenantName(tenantURL)),
		Key:         token,
		Status:      1,
		Models:      channelTypeModels[channelType],
		BaseURL:     &tenantURL,
		Group:       "default",
		CreatedTime: time.Now().Unix(),
	}
	if insertErr := newCh.Insert(); insertErr != nil {
		return fmt.Errorf("auto-create ACE channel failed: %v", insertErr)
	}
	common.SysLog(fmt.Sprintf("Auto-created ACE channel for tenant '%s'", tenantURL))
	return nil
}

// extractTenantName 从 tenantURL 提取简短名称
func extractTenantName(tenantURL string) string {
	// https://d16.api.augmentcode.com/ → d16
	tenantURL = strings.TrimRight(tenantURL, "/")
	tenantURL = strings.TrimPrefix(tenantURL, "https://")
	tenantURL = strings.TrimPrefix(tenantURL, "http://")
	parts := strings.Split(tenantURL, ".")
	if len(parts) > 0 {
		return parts[0]
	}
	return tenantURL
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

// channelTypeModels 各渠道类型对应的模型列表
var channelTypeModels = map[int]string{
	constant.ChannelTypeExa:     "exa-search,exa-contents,exa-find-similar,exa-answer",
	constant.ChannelTypeTavily:  "tavily-search,tavily-extract,tavily-crawl,tavily-map",
	constant.ChannelTypeAugment: "augment-codebase-retrieval",
}

// channelTypeNames 各渠道类型对应的渠道名称
var channelTypeNames = map[int]string{
	constant.ChannelTypeExa:     "Exa (Auto)",
	constant.ChannelTypeTavily:  "Tavily (Auto)",
	constant.ChannelTypeAugment: "Augment (Auto)",
}

// appendKeyToChannel 将 Key 追加到指定类型的第一个 Channel
// 如果该类型没有 Channel，自动创建一个（多 key 轮询模式）
func appendKeyToChannel(channelType int, key string) error {
	channels, err := model.GetChannelsByType(0, 1, false, channelType)
	if err != nil || len(channels) == 0 {
		// 自动创建渠道
		common.SysLog(fmt.Sprintf("No channel found for type %d, auto-creating...", channelType))
		emptyStr := ""
		newCh := &model.Channel{
			Type:        channelType,
			Name:        channelTypeNames[channelType],
			Key:         key,
			Status:      1,
			Models:      channelTypeModels[channelType],
			BaseURL:     &emptyStr, // 空字符串让 GetBaseURL() 自动从 ChannelBaseURLs 取默认值
			Group:       "default",
			CreatedTime: time.Now().Unix(),
		}
		if insertErr := newCh.Insert(); insertErr != nil {
			return fmt.Errorf("auto-create channel failed: %v", insertErr)
		}
		common.SysLog(fmt.Sprintf("Auto-created channel '%s' (type=%d) with first key", newCh.Name, channelType))
		return nil
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

