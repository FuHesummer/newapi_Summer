package augment

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"strings"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/dto"
	"github.com/QuantumNous/new-api/relay/channel"
	relaycommon "github.com/QuantumNous/new-api/relay/common"
	"github.com/QuantumNous/new-api/types"
	"github.com/gin-gonic/gin"
	"github.com/google/uuid"
)

type Adaptor struct{}

func (a *Adaptor) Init(info *relaycommon.RelayInfo) {}

func (a *Adaptor) GetRequestURL(info *relaycommon.RelayInfo) (string, error) {
	path := info.RequestURLPath
	if path == "" {
		return "", errors.New("empty request path")
	}
	// 映射端点路径
	upstreamPath, ok := endpointMapping[path]
	if !ok {
		return "", fmt.Errorf("unknown augment endpoint: %s", path)
	}
	return fmt.Sprintf("%s%s", info.ChannelBaseUrl, upstreamPath), nil
}

func (a *Adaptor) SetupRequestHeader(c *gin.Context, req *http.Header, info *relaycommon.RelayInfo) error {
	// 不调用 channel.SetupApiRequestHeader — 需要完全控制请求头
	// acemcp-relay 会过滤掉客户端传来的所有敏感头，只保留安全的头
	req.Set("Authorization", "Bearer "+info.ApiKey)
	req.Set("Content-Type", "application/json")
	req.Set("Accept", "application/json")

	// 伪装 CLI/插件 请求头（关键：每个请求随机生成，模拟不同用户/会话）
	req.Set("User-Agent", GetRandomUA())
	req.Set("X-Request-Id", GenerateID())
	req.Set("X-Request-Session-Id", GenerateID())

	// 过滤掉客户端传入的危险头（防止泄露真实信息或干扰上游）
	// 参考 acemcp-relay 的 skipRequestHeaders
	for _, h := range []string{
		"X-Forwarded-For", "X-Forwarded-Proto", "X-Forwarded-Host",
		"X-Real-Ip", "X-Original-Uri", "Via",
		"Sentry-Trace", "Baggage",
		"Proxy-Authorization", "Proxy-Connection",
	} {
		req.Del(h)
	}

	return nil
}

func (a *Adaptor) ConvertOpenAIRequest(c *gin.Context, info *relaycommon.RelayInfo, request *dto.GeneralOpenAIRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertRerankRequest(c *gin.Context, relayMode int, request dto.RerankRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertEmbeddingRequest(c *gin.Context, info *relaycommon.RelayInfo, request dto.EmbeddingRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertAudioRequest(c *gin.Context, info *relaycommon.RelayInfo, request dto.AudioRequest) (io.Reader, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertImageRequest(c *gin.Context, info *relaycommon.RelayInfo, request dto.ImageRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertOpenAIResponsesRequest(c *gin.Context, info *relaycommon.RelayInfo, request dto.OpenAIResponsesRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertClaudeRequest(c *gin.Context, info *relaycommon.RelayInfo, request *dto.ClaudeRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) ConvertGeminiRequest(c *gin.Context, info *relaycommon.RelayInfo, request *dto.GeminiChatRequest) (any, error) {
	return nil, errors.New("not implemented")
}

func (a *Adaptor) DoRequest(c *gin.Context, info *relaycommon.RelayInfo, requestBody io.Reader) (any, error) {
	return channel.DoApiRequest(a, c, info, requestBody)
}

func (a *Adaptor) DoResponse(c *gin.Context, resp *http.Response, info *relaycommon.RelayInfo) (usage any, err *types.NewAPIError) {
	path := info.RequestURLPath

	// 拦截端点 → 直接返回 200，不转发到上游（防 trace）
	if interceptedEndpoints[path] {
		defer resp.Body.Close()
		c.JSON(http.StatusOK, gin.H{})
		return nil, nil
	}

	// SSE 流式端点 → 流式转发
	if sseEndpoints[path] {
		return a.handleSSEResponse(c, resp, info)
	}

	// /get-models → 脱敏处理
	if path == "/augment/get-models" {
		return a.handleGetModelsResponse(c, resp, info)
	}

	// 其他端点 → 直接透传
	return a.handleDirectResponse(c, resp, info)
}

// handleSSEResponse 处理 SSE 流式响应
func (a *Adaptor) handleSSEResponse(c *gin.Context, resp *http.Response, info *relaycommon.RelayInfo) (any, *types.NewAPIError) {
	defer resp.Body.Close()

	// 设置 SSE 响应头
	c.Writer.Header().Set("Content-Type", "text/event-stream")
	c.Writer.Header().Set("Cache-Control", "no-cache")
	c.Writer.Header().Set("Connection", "keep-alive")
	c.Writer.WriteHeader(resp.StatusCode)

	scanner := bufio.NewScanner(resp.Body)
	scanner.Buffer(make([]byte, 0), 1024*1024)
	for scanner.Scan() {
		line := scanner.Text()
		_, writeErr := fmt.Fprintf(c.Writer, "%s\n", line)
		if writeErr != nil {
			break
		}
		c.Writer.Flush()
	}

	return nil, nil
}

// handleGetModelsResponse 处理 /get-models 响应并脱敏
func (a *Adaptor) handleGetModelsResponse(c *gin.Context, resp *http.Response, info *relaycommon.RelayInfo) (any, *types.NewAPIError) {
	defer resp.Body.Close()

	body, readErr := io.ReadAll(resp.Body)
	if readErr != nil {
		return nil, &types.NewAPIError{
			StatusCode: http.StatusInternalServerError,
		}
	}

	// 尝试脱敏
	var responseData map[string]interface{}
	if common.Unmarshal(body, &responseData) == nil {
		sanitizeModelResponse(responseData)
		sanitizedBody, err := common.Marshal(responseData)
		if err == nil {
			body = sanitizedBody
		}
	}

	c.Data(resp.StatusCode, "application/json", body)
	return nil, nil
}

// handleDirectResponse 直接透传响应（过滤危险响应头）
func (a *Adaptor) handleDirectResponse(c *gin.Context, resp *http.Response, info *relaycommon.RelayInfo) (any, *types.NewAPIError) {
	defer resp.Body.Close()

	// 参考 acemcp-relay 的 skipResponseHeaders，过滤 hop-by-hop 和代理头
	skipHeaders := map[string]bool{
		"Connection":          true,
		"Keep-Alive":          true,
		"Transfer-Encoding":   true,
		"Te":                  true,
		"Trailer":             true,
		"Upgrade":             true,
		"Proxy-Authorization": true,
		"Proxy-Authenticate":  true,
		"Content-Length":      true,
		"Content-Encoding":    true,
		"Alt-Svc":             true,
	}

	for k, v := range resp.Header {
		if skipHeaders[k] {
			continue
		}
		for _, vv := range v {
			c.Writer.Header().Add(k, vv)
		}
	}
	c.Writer.WriteHeader(resp.StatusCode)
	io.Copy(c.Writer, resp.Body)
	return nil, nil
}

// sanitizeModelResponse 脱敏 /get-models 响应中的用户信息
func sanitizeModelResponse(data map[string]interface{}) {
	if user, ok := data["user"].(map[string]interface{}); ok {
		user["id"] = uuid.New().String()
		user["email"] = generateRandomEmail()
		user["tenant_id"] = generateRandomHex(32)
		user["tenant_name"] = fmt.Sprintf("t-%s", generateRandomHex(8))
	}
}

func generateRandomEmail() string {
	chars := "abcdefghijklmnopqrstuvwxyz0123456789"
	name := make([]byte, 8)
	for i := range name {
		name[i] = chars[rand.Intn(len(chars))]
	}
	domains := []string{"gmail.com", "outlook.com", "yahoo.com"}
	return fmt.Sprintf("%s@%s", string(name), domains[rand.Intn(len(domains))])
}

func generateRandomHex(length int) string {
	chars := "0123456789abcdef"
	result := make([]byte, length)
	for i := range result {
		result[i] = chars[rand.Intn(len(chars))]
	}
	return string(result)
}

func (a *Adaptor) GetModelList() []string {
	return ModelList
}

func (a *Adaptor) GetChannelName() string {
	return ChannelName
}

// IsInterceptedEndpoint 判断端点是否需要拦截（不转发）
func IsInterceptedEndpoint(path string) bool {
	return interceptedEndpoints[path]
}

// IsSSEEndpoint 判断端点是否为 SSE 流式端点
func IsSSEEndpoint(path string) bool {
	return sseEndpoints[path]
}

// SanitizePath 清理路径前缀
func SanitizePath(path string) string {
	return strings.TrimPrefix(path, "/augment")
}
