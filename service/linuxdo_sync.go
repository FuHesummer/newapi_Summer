package service

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/QuantumNous/new-api/common"
)

// FetchLinuxDOTrustLevel 通过 LinuxDO API 获取用户的 trust_level
// linuxDOId 是用户在 LinuxDO 上的数字 ID
func FetchLinuxDOTrustLevel(linuxDOId string) (int, error) {
	if linuxDOId == "" {
		return 0, fmt.Errorf("linuxdo id is empty")
	}

	// LinuxDO 公开用户信息 API
	userEndpoint := common.GetEnvOrDefaultString("LINUX_DO_USER_PUBLIC_ENDPOINT", "https://linux.do")
	apiURL := fmt.Sprintf("%s/u/by-external/%s.json", userEndpoint, linuxDOId)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", apiURL, nil)
	if err != nil {
		return 0, fmt.Errorf("create request failed: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	// 使用 LinuxDO API key 如果配置了
	apiKey := common.GetEnvOrDefaultString("LINUX_DO_API_KEY", "")
	if apiKey != "" {
		req.Header.Set("Api-Key", apiKey)
		req.Header.Set("Api-Username", "system")
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return 0, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return 0, fmt.Errorf("API returned status %d", resp.StatusCode)
	}

	var result struct {
		User struct {
			TrustLevel int `json:"trust_level"`
		} `json:"user"`
	}
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return 0, fmt.Errorf("decode response failed: %w", err)
	}

	return result.User.TrustLevel, nil
}
