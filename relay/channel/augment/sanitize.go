package augment

import (
	"fmt"
	"math/rand"

	"github.com/QuantumNous/new-api/common"
	"github.com/google/uuid"
)

// SanitizeGetModelsResponse 脱敏 /get-models 响应
func SanitizeGetModelsResponse(body []byte) []byte {
	var data map[string]interface{}
	if common.Unmarshal(body, &data) != nil {
		return body
	}
	if user, ok := data["user"].(map[string]interface{}); ok {
		user["id"] = uuid.New().String()
		user["email"] = randomEmail()
		user["tenant_id"] = randomHex(32)
		user["tenant_name"] = fmt.Sprintf("t-%s", randomHex(8))
	}
	sanitized, err := common.Marshal(data)
	if err != nil {
		return body
	}
	return sanitized
}

func randomEmail() string {
	chars := "abcdefghijklmnopqrstuvwxyz0123456789"
	name := make([]byte, 8)
	for i := range name {
		name[i] = chars[rand.Intn(len(chars))]
	}
	domains := []string{"gmail.com", "outlook.com", "yahoo.com"}
	return fmt.Sprintf("%s@%s", string(name), domains[rand.Intn(len(domains))])
}

func randomHex(length int) string {
	chars := "0123456789abcdef"
	result := make([]byte, length)
	for i := range result {
		result[i] = chars[rand.Intn(len(chars))]
	}
	return string(result)
}
