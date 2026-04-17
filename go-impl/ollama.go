package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

// OllamaAdapter — mirrors the Python OllamaAdapter. Talks HTTP to
// localhost:11434/api/chat, asks for JSON mode, tolerantly parses the
// (value, confidence) shape from the response. No third-party deps.
type OllamaAdapter struct {
	Model   string
	Host    string
	Timeout time.Duration
}

func NewOllamaAdapter() *OllamaAdapter {
	model := os.Getenv("AIL_OLLAMA_MODEL")
	if model == "" {
		model = "llama3.1:latest"
	}
	host := os.Getenv("AIL_OLLAMA_HOST")
	if host == "" {
		host = "http://localhost:11434"
	}
	return &OllamaAdapter{Model: model, Host: strings.TrimRight(host, "/"), Timeout: 120 * time.Second}
}

type ollamaChatReq struct {
	Model    string                 `json:"model"`
	Messages []ollamaMsg            `json:"messages"`
	Stream   bool                   `json:"stream"`
	Format   string                 `json:"format"`
	Options  map[string]interface{} `json:"options"`
}

type ollamaMsg struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type ollamaChatResp struct {
	Message ollamaMsg `json:"message"`
}

func (a *OllamaAdapter) Invoke(goal string, constraints []string, inputs map[string]interface{}) (Value, string, error) {
	system := buildSystemPrompt(goal, constraints)
	user := buildUserPrompt(inputs)

	req := ollamaChatReq{
		Model: a.Model,
		Messages: []ollamaMsg{
			{Role: "system", Content: system},
			{Role: "user", Content: user},
		},
		Stream:  false,
		Format:  "json",
		Options: map[string]interface{}{"temperature": 0.0},
	}
	body, err := json.Marshal(req)
	if err != nil {
		return Value{}, "", err
	}

	client := &http.Client{Timeout: a.Timeout}
	httpReq, err := http.NewRequest("POST", a.Host+"/api/chat", bytes.NewReader(body))
	if err != nil {
		return Value{}, "", err
	}
	httpReq.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(httpReq)
	if err != nil {
		return Value{}, "", fmt.Errorf("ollama request failed: %w (is `ollama serve` running and model %q pulled?)", err, a.Model)
	}
	defer resp.Body.Close()
	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return Value{}, "", err
	}

	var chat ollamaChatResp
	if err := json.Unmarshal(raw, &chat); err != nil {
		return Value{}, "", fmt.Errorf("ollama: unexpected response shape: %w", err)
	}

	value, confidence := parseValueConfidence(chat.Message.Content)
	return Value{V: value, Conf: confidence}, "ollama/" + a.Model, nil
}

func buildSystemPrompt(goal string, constraints []string) string {
	var b strings.Builder
	b.WriteString("You are executing an AIL intent. AIL programs describe *intent*;\n")
	b.WriteString("you produce the result that satisfies the declared goal and constraints.\n\n")
	b.WriteString("Respond with ONE JSON object and nothing else:\n")
	b.WriteString(`  {"value": <result>, "confidence": <float 0.0 to 1.0>}` + "\n\n")
	b.WriteString("The confidence reflects your calibrated belief the result meets\n")
	b.WriteString("the goal. 1.0 = certain; 0.5 = unsure; 0.0 = could not satisfy.\n\n")
	b.WriteString("GOAL: ")
	b.WriteString(goal)
	b.WriteString("\n")
	if len(constraints) > 0 {
		b.WriteString("\nCONSTRAINTS:\n")
		for _, c := range constraints {
			b.WriteString("  - ")
			b.WriteString(c)
			b.WriteByte('\n')
		}
	}
	return b.String()
}

func buildUserPrompt(inputs map[string]interface{}) string {
	if len(inputs) == 0 {
		return "(no input)"
	}
	var b strings.Builder
	for k, v := range inputs {
		b.WriteString(k)
		b.WriteString(": ")
		b.WriteString(fmt.Sprintf("%v", v))
		b.WriteByte('\n')
	}
	return strings.TrimRight(b.String(), "\n")
}

// parseValueConfidence — tolerant (value, confidence) extractor, matching
// the Python shared parser. Handles pure JSON, code-fenced JSON, JSON
// embedded in prose, and confidence clamping.
func parseValueConfidence(text string) (interface{}, float64) {
	stripped := stripCodeFence(strings.TrimSpace(text))

	var obj map[string]interface{}
	if err := json.Unmarshal([]byte(stripped), &obj); err == nil {
		if v, ok := obj["value"]; ok {
			c := clampConfidence(obj["confidence"])
			return normalizeJSONValue(v), c
		}
	}
	// Embedded-JSON fallback: find first balanced {...} containing "value".
	if cand := extractBalancedJSON(stripped); cand != "" {
		if err := json.Unmarshal([]byte(cand), &obj); err == nil {
			if v, ok := obj["value"]; ok {
				c := clampConfidence(obj["confidence"])
				return normalizeJSONValue(v), c
			}
		}
	}
	return text, 0.5
}

func normalizeJSONValue(v interface{}) interface{} {
	// Numbers come back as float64 (good). Strings / bools pass through.
	// Nested objects / arrays remain as-is — intents typically return a
	// scalar for this v0.
	return v
}

func clampConfidence(raw interface{}) float64 {
	switch x := raw.(type) {
	case float64:
		if x < 0 {
			return 0
		}
		if x > 1 {
			return 1
		}
		return x
	case string:
		// Not numeric per JSON, but some models emit "0.9" as a string.
		return 0.5
	case nil:
		return 0.5
	}
	return 0.5
}

func stripCodeFence(text string) string {
	s := strings.TrimSpace(text)
	if !strings.HasPrefix(s, "```") {
		return s
	}
	nl := strings.IndexByte(s, '\n')
	if nl < 0 {
		return s
	}
	body := s[nl+1:]
	body = strings.TrimSuffix(body, "```")
	return strings.TrimSpace(body)
}

func extractBalancedJSON(text string) string {
	// Find first balanced {...} substring that contains `"value"`.
	for start, c := range text {
		if c != '{' {
			continue
		}
		depth := 0
		inStr := false
		esc := false
		for i := start; i < len(text); i++ {
			ch := text[i]
			if inStr {
				if esc {
					esc = false
				} else if ch == '\\' {
					esc = true
				} else if ch == '"' {
					inStr = false
				}
				continue
			}
			if ch == '"' {
				inStr = true
			} else if ch == '{' {
				depth++
			} else if ch == '}' {
				depth--
				if depth == 0 {
					cand := text[start : i+1]
					if strings.Contains(cand, `"value"`) {
						return cand
					}
					break
				}
			}
		}
	}
	return ""
}
