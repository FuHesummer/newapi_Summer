package registrar

import (
	"bytes"
	"fmt"
	"net/http"
	"time"

	"github.com/QuantumNous/new-api/common"
)

// Client 注册机 sidecar HTTP 客户端
type Client struct {
	BaseURL    string
	HTTPClient *http.Client
}

// KeyResult 注册返回的 Key 信息
type KeyResult struct {
	Email    string `json:"email"`
	APIKey   string `json:"api_key"`
	Provider string `json:"provider"`
}

// RegisterResponse sidecar 注册响应
type RegisterResponse struct {
	Success    bool        `json:"success"`
	Total      int         `json:"total"`
	Successful int         `json:"successful"`
	Failed     int         `json:"failed"`
	Keys       []KeyResult `json:"keys"`
}

// DomainStatus 域名熔断状态
type DomainStatus struct {
	Domain           string `json:"domain"`
	Status           string `json:"status"`
	Success          int    `json:"success"`
	Fail             int    `json:"fail"`
	ConsecutiveFails int    `json:"consecutive_fails"`
	RemainingSeconds int    `json:"remaining_seconds"`
}

func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 5 * time.Minute,
		},
	}
}

// RegisterTavily 调用 sidecar 注册 Tavily 账号（旧的 count 模式）
func (c *Client) RegisterTavily(count int, proxy string) (*RegisterResponse, error) {
	body := fmt.Sprintf(`{"count":%d,"proxy":"%s"}`, count, proxy)
	resp, err := c.HTTPClient.Post(
		c.BaseURL+"/register/tavily",
		"application/json",
		bytes.NewReader([]byte(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("sidecar request failed: %w", err)
	}
	defer resp.Body.Close()

	var result RegisterResponse
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return nil, fmt.Errorf("sidecar response decode failed: %w", err)
	}
	return &result, nil
}

// RegisterTavilyWithAccounts 调用 sidecar 使用 Google 账号批量注册 Tavily
func (c *Client) RegisterTavilyWithAccounts(accounts string, proxy string) (*RegisterResponse, error) {
	reqBody := struct {
		Accounts string `json:"accounts"`
		Proxy    string `json:"proxy,omitempty"`
	}{
		Accounts: accounts,
		Proxy:    proxy,
	}
	bodyBytes, err := common.Marshal(reqBody)
	if err != nil {
		return nil, fmt.Errorf("marshal request failed: %w", err)
	}

	resp, err := c.HTTPClient.Post(
		c.BaseURL+"/register/tavily",
		"application/json",
		bytes.NewReader(bodyBytes),
	)
	if err != nil {
		return nil, fmt.Errorf("sidecar request failed: %w", err)
	}
	defer resp.Body.Close()

	var result RegisterResponse
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return nil, fmt.Errorf("sidecar response decode failed: %w", err)
	}
	return &result, nil
}

// RegisterExa 调用 sidecar 注册 Exa 账号
func (c *Client) RegisterExa(count int, proxy string) (*RegisterResponse, error) {
	body := fmt.Sprintf(`{"count":%d,"proxy":"%s"}`, count, proxy)
	resp, err := c.HTTPClient.Post(
		c.BaseURL+"/register/exa",
		"application/json",
		bytes.NewReader([]byte(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("sidecar request failed: %w", err)
	}
	defer resp.Body.Close()

	var result RegisterResponse
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return nil, fmt.Errorf("sidecar response decode failed: %w", err)
	}
	return &result, nil
}

// RegisterAce 调用 sidecar 注册 Augment Code 账号
func (c *Client) RegisterAce(count int, proxy string) (*RegisterResponse, error) {
	body := fmt.Sprintf(`{"count":%d,"proxy":"%s"}`, count, proxy)
	resp, err := c.HTTPClient.Post(
		c.BaseURL+"/register/ace",
		"application/json",
		bytes.NewReader([]byte(body)),
	)
	if err != nil {
		return nil, fmt.Errorf("sidecar request failed: %w", err)
	}
	defer resp.Body.Close()

	var result RegisterResponse
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return nil, fmt.Errorf("sidecar response decode failed: %w", err)
	}
	return &result, nil
}

// Health 健康检查
func (c *Client) Health() error {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/health")
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return fmt.Errorf("sidecar unhealthy: status %d", resp.StatusCode)
	}
	return nil
}

// GetDomainStatus 获取域名熔断状态
func (c *Client) GetDomainStatus() ([]DomainStatus, error) {
	resp, err := c.HTTPClient.Get(c.BaseURL + "/domains")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	var result struct {
		Domains []DomainStatus `json:"domains"`
	}
	if err := common.DecodeJson(resp.Body, &result); err != nil {
		return nil, err
	}
	return result.Domains, nil
}
