# A2A Contract Tests

This directory contains consumer-driven contract testing specifications for the A2A (Agent-to-Agent) JSON-RPC 2.0 API.

## Purpose

Contract tests verify that agents comply with the A2A protocol specification. These tests define the expected behavior and responses for each agent endpoint, ensuring interoperability between agents and consumers.

## Structure

Contract files in this directory define expected API behavior for:

- **Request format**: JSON-RPC 2.0 compliant requests
- **Response format**: Expected result structures and error codes
- **Agent endpoints**: Specific methods each agent must implement

## Agents Under Test

### Liturgy Agent
- `agent.ping` - Health check
- `liturgy_agent.get_readings` - Fetch liturgical readings
- `liturgy_agent.get_lectionary` - Get sacrament lectionary

### Homily Agent
- `agent.ping` - Health check
- `homily_agent.generate` - Generate homily content
- `homily_agent.refine` - Refine homily based on feedback

## Contract Testing Approach

Consumer-driven contract testing ensures:
1. Agents produce responses that consumers expect
2. Breaking changes are detected before deployment
3. API documentation stays synchronized with implementation

## Related

- Protocol definition: `packages/a2a-protocol/`
- Agent implementations: `packages/liturgy-agent/`, `packages/homily-agent/`
- Consumer: `packages/chat-orchestrator/`