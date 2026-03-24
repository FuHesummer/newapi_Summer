package service

import (
	"fmt"
	"time"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/pkg/registrar"
	"github.com/QuantumNous/new-api/setting"
	"github.com/bytedance/gopkg/util/gopool"
)

// StartRegistrarAutoReplenish 启动注册机自动补号后台任务
func StartRegistrarAutoReplenish() {
	gopool.Go(func() {
		// 等待系统完全启动
		time.Sleep(30 * time.Second)
		common.SysLog("Registrar auto-replenish task started")

		for {
			cfg := setting.GetRegistrarSetting()
			interval := cfg.CheckIntervalMin
			if interval <= 0 {
				interval = 30
			}

			if cfg.Enabled && cfg.AutoReplenish {
				checkAndReplenish(cfg)
			}

			time.Sleep(time.Duration(interval) * time.Minute)
		}
	})
}

// checkAndReplenish 检查水位线并自动补号
func checkAndReplenish(cfg *setting.RegistrarSetting) {
	client := registrar.NewClient(cfg.SidecarURL)

	// 检查 Exa
	if cfg.ExaMinKeys > 0 {
		exaCount := countActiveKeys(58)
		if exaCount < cfg.ExaMinKeys {
			need := cfg.ExaMinKeys - exaCount
			common.SysLog(fmt.Sprintf("Exa below waterline: %d/%d, registering %d keys...", exaCount, cfg.ExaMinKeys, need))
			result, err := client.RegisterExa(need, cfg.RegistrationProxy)
			if err != nil {
				common.SysError(fmt.Sprintf("Exa auto-replenish failed: %s", err.Error()))
			} else {
				imported := 0
				for _, key := range result.Keys {
					if key.APIKey != "" {
						if err := appendKeyToChannelAuto(58, key.APIKey); err != nil {
							common.SysError(fmt.Sprintf("Failed to import Exa key: %s", err.Error()))
						} else {
							imported++
						}
					}
				}
				common.SysLog(fmt.Sprintf("Exa auto-replenish: registered %d, imported %d", result.Successful, imported))
			}
		}
	}
}

// countActiveKeys 统计某类型渠道的活跃 key 数量
func countActiveKeys(channelType int) int {
	channels, err := model.GetChannelsByType(0, 100, false, channelType)
	if err != nil {
		return 0
	}

	total := 0
	for _, ch := range channels {
		fullCh, err := model.GetChannelById(ch.Id, true)
		if err != nil {
			continue
		}
		if fullCh.Key != "" {
			keys := splitKeys(fullCh.Key)
			total += len(keys)
		}
	}
	return total
}

// splitKeys 按换行符分割 key
func splitKeys(key string) []string {
	var result []string
	for _, k := range splitByNewline(key) {
		k = trimSpace(k)
		if k != "" {
			result = append(result, k)
		}
	}
	return result
}

func splitByNewline(s string) []string {
	var result []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			result = append(result, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		result = append(result, s[start:])
	}
	return result
}

func trimSpace(s string) string {
	i := 0
	for i < len(s) && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r') {
		i++
	}
	j := len(s)
	for j > i && (s[j-1] == ' ' || s[j-1] == '\t' || s[j-1] == '\r') {
		j--
	}
	return s[i:j]
}

// appendKeyToChannelAuto 追加 key 到渠道（自动创建）
// 复用 controller 里的逻辑，但这里在 service 层
func appendKeyToChannelAuto(channelType int, key string) error {
	channels, err := model.GetChannelsByType(0, 1, false, channelType)
	if err != nil || len(channels) == 0 {
		// 自动创建
		channelNames := map[int]string{58: "Exa (Auto)", 59: "Tavily (Auto)", 60: "Augment (Auto)"}
		channelModels := map[int]string{
			58: "exa-search,exa-contents,exa-find-similar,exa-answer",
			59: "tavily-search,tavily-extract,tavily-crawl,tavily-map",
			60: "augment-chat,augment-codebase-retrieval",
		}
		emptyStr := ""
		newCh := &model.Channel{
			Type:        channelType,
			Name:        channelNames[channelType],
			Key:         key,
			Status:      1,
			Models:      channelModels[channelType],
			BaseURL:     &emptyStr,
			Group:       "default",
			CreatedTime: time.Now().Unix(),
		}
		return newCh.Insert()
	}

	ch := channels[0]
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
