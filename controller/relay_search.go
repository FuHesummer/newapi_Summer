package controller

import (
	"bytes"
	"fmt"
	"io"
	"net/http"

	"github.com/QuantumNous/new-api/common"
	"github.com/QuantumNous/new-api/model"
	"github.com/QuantumNous/new-api/relay/channel/augment"
	"github.com/gin-gonic/gin"
)

// SearchAPIRelay 通用搜索 API 透传 Controller
// 用于 Exa / Tavily / Augment（非 SSE）端点的请求透传
func SearchAPIRelay(c *gin.Context) {
	channelType := c.GetInt("channel_type")
	channelId := c.GetInt("channel_id")
	channelBaseUrl := c.GetString("channel_base_url")
	apiKey := c.GetString("api_key")
	userId := c.GetInt("id")
	tokenId := c.GetInt("token_id")
	tokenName := c.GetString("token_name")
	group := c.GetString("group")

	if channelBaseUrl == "" || apiKey == "" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "channel not configured"})
		return
	}

	// 读取请求体
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "failed to read request body"})
		return
	}
	defer c.Request.Body.Close()

	// 构建上游 URL
	upstreamURL := channelBaseUrl + c.Request.URL.Path

	// 构建上游请求
	req, err := http.NewRequestWithContext(c.Request.Context(), "POST", upstreamURL, io.NopCloser(io.Reader(nil)))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "failed to create upstream request"})
		return
	}

	// 设置请求体
	req.Body = io.NopCloser(io.Reader(nil))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	// 根据渠道类型设置认证头
	switch channelType {
	case 58: // Exa
		req.Header.Set("x-api-key", apiKey)
	case 59: // Tavily
		req.Header.Set("Authorization", "Bearer "+apiKey)
	case 60: // Augment
		req.Header.Set("Authorization", "Bearer "+apiKey)
		req.Header.Set("User-Agent", augment.GetRandomUA())
	}

	// 重新构建请求（使用原始 body）
	upstreamReq, err := http.NewRequestWithContext(c.Request.Context(), "POST", upstreamURL, io.NopCloser(bytesReader(body)))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "failed to create request"})
		return
	}
	upstreamReq.Header = req.Header

	// 发送请求
	client := &http.Client{}
	resp, err := client.Do(upstreamReq)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"success": false, "message": "upstream request failed: " + err.Error()})
		return
	}
	defer resp.Body.Close()

	// 记录日志
	model.RecordLog(userId, model.LogTypeConsume,
		fmt.Sprintf("SearchAPI relay: channel=%d path=%s status=%d token=%s group=%s",
			channelId, c.Request.URL.Path, resp.StatusCode, tokenName, group))

	// 处理上游错误 — 自动禁用 Key
	if resp.StatusCode == 401 || resp.StatusCode == 403 {
		common.SysLog(fmt.Sprintf("SearchAPI: upstream returned %d for channel %d, key may be invalid",
			resp.StatusCode, channelId))
	}

	// 透传响应
	respBody, _ := io.ReadAll(resp.Body)
	for k, v := range resp.Header {
		for _, vv := range v {
			c.Writer.Header().Add(k, vv)
		}
	}
	c.Data(resp.StatusCode, resp.Header.Get("Content-Type"), respBody)

	_ = tokenId // 用于后续计费扩展
}

// AugmentAPIRelay Augment 专用 Controller（含 SSE 流式和脱敏）
func AugmentAPIRelay(c *gin.Context) {
	channelBaseUrl := c.GetString("channel_base_url")
	apiKey := c.GetString("api_key")
	userId := c.GetInt("id")
	tokenName := c.GetString("token_name")
	channelId := c.GetInt("channel_id")

	if channelBaseUrl == "" || apiKey == "" {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "channel not configured"})
		return
	}

	path := c.Request.URL.Path

	// 读取请求体
	body, err := io.ReadAll(c.Request.Body)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"success": false, "message": "failed to read request body"})
		return
	}
	defer c.Request.Body.Close()

	// 映射上游路径
	upstreamPath := augment.SanitizePath(path)
	// /codebase-retrieval → /agents/codebase-retrieval
	if upstreamPath == "/codebase-retrieval" {
		upstreamPath = "/agents/codebase-retrieval"
	}
	upstreamURL := channelBaseUrl + upstreamPath

	// 构建上游请求
	upstreamReq, err := http.NewRequestWithContext(c.Request.Context(), "POST", upstreamURL, io.NopCloser(bytesReader(body)))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"success": false, "message": "failed to create request"})
		return
	}

	upstreamReq.Header.Set("Content-Type", "application/json")
	upstreamReq.Header.Set("Accept", "application/json")
	upstreamReq.Header.Set("Authorization", "Bearer "+apiKey)
	upstreamReq.Header.Set("User-Agent", augment.GetRandomUA())
	upstreamReq.Header.Set("X-Request-Id", augment.GenerateID())
	upstreamReq.Header.Set("X-Request-Session-Id", augment.GenerateID())

	// SSE 端点
	if augment.IsSSEEndpoint(path) {
		upstreamReq.Header.Set("Accept", "text/event-stream")
	}

	client := &http.Client{}
	resp, err := client.Do(upstreamReq)
	if err != nil {
		c.JSON(http.StatusBadGateway, gin.H{"success": false, "message": "upstream request failed"})
		return
	}
	defer resp.Body.Close()

	model.RecordLog(userId, model.LogTypeConsume,
		fmt.Sprintf("Augment relay: channel=%d path=%s status=%d token=%s",
			channelId, path, resp.StatusCode, tokenName))

	// SSE 流式转发
	if augment.IsSSEEndpoint(path) {
		c.Writer.Header().Set("Content-Type", "text/event-stream")
		c.Writer.Header().Set("Cache-Control", "no-cache")
		c.Writer.Header().Set("Connection", "keep-alive")
		c.Writer.WriteHeader(resp.StatusCode)
		io.Copy(c.Writer, resp.Body)
		c.Writer.Flush()
		return
	}

	// /get-models 脱敏
	respBody, _ := io.ReadAll(resp.Body)
	if path == "/augment/get-models" {
		respBody = augment.SanitizeGetModelsResponse(respBody)
	}

	for k, v := range resp.Header {
		for _, vv := range v {
			c.Writer.Header().Add(k, vv)
		}
	}
	c.Data(resp.StatusCode, "application/json", respBody)
}

// AugmentInterceptRelay 拦截 Augment 追踪端点（返回空 200）
func AugmentInterceptRelay(c *gin.Context) {
	c.JSON(http.StatusOK, gin.H{})
}

// bytesReader 从 []byte 创建 io.Reader
func bytesReader(b []byte) io.Reader {
	return bytes.NewReader(b)
}
