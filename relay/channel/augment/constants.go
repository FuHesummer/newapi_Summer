package augment

import (
	"math/rand"
	"time"

	"github.com/google/uuid"
)

var ModelList = []string{
	"augment-chat",
	"augment-codebase-retrieval",
}

var ChannelName = "augment"

// 伪造 User-Agent 列表（模拟 Augment CLI 和 VS Code 插件）
// 参考 acemcp-relay 的 fakeUserAgents，保持与官方客户端版本一致
var fakeUserAgents = []string{
	"augment.cli/0.15.0 (commit 8c3839b5)/interactive",
	"augment.cli/0.14.2 (commit a1b2c3d4)/interactive",
	"augment.cli/0.16.1 (commit d5e6f7a8)/interactive",
	"Augment.vscode-augment/0.754.3 (darwin; arm64; 25.2.0) vscode/1.109.2",
	"Augment.vscode-augment/0.750.1 (linux; x64; 25.1.0) vscode/1.108.0",
	"Augment.vscode-augment/0.748.0 (win32; x64; 25.1.0) vscode/1.107.1",
	"Augment.vscode-augment/0.756.0 (darwin; x64; 25.2.0) vscode/1.110.0",
	"Augment.vscode-augment/0.752.2 (linux; arm64; 25.1.0) vscode/1.109.0",
}

// 端点路径映射：new-api 路径 → 上游路径
var endpointMapping = map[string]string{
	"/augment/chat-stream":           "/chat-stream",
	"/augment/codebase-retrieval":    "/agents/codebase-retrieval",
	"/augment/get-models":            "/get-models",
	"/augment/prompt-enhancer":       "/prompt-enhancer",
	"/augment/batch-upload":          "/batch-upload",
	"/augment/find-missing":          "/find-missing",
	"/augment/record-request-events": "/record-request-events",
	"/augment/report-error":          "/report-error",
}

// 需要拦截（不转发到上游）的端点
var interceptedEndpoints = map[string]bool{
	"/augment/record-request-events": true,
	"/augment/report-error":          true,
	"/augment/prompt-enhancer":       true, // 提示词增强会扣额度，拦截
}

// SSE 流式端点
var sseEndpoints = map[string]bool{
	"/augment/chat-stream": true,
}

func GetRandomUA() string {
	return fakeUserAgents[rand.Intn(len(fakeUserAgents))]
}

func GenerateID() string {
	return uuid.New().String()
}

func init() {
	rand.New(rand.NewSource(time.Now().UnixNano()))
}
