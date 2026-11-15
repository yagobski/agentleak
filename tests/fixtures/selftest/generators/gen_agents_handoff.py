# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
import json
import sys

from agents import Agent, Model, ModelResponse, Runner, Usage, set_tracing_disabled
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

set_tracing_disabled(True)


class Triage(Model):
    async def get_response(self, *a, **k):
        return ModelResponse(
            output=[
                ResponseFunctionToolCall(
                    type="function_call",
                    id="fc_h",
                    call_id="call_h",
                    name="transfer_to_billing",
                    arguments="{}",
                    status="completed",
                )
            ],
            usage=Usage(),
            response_id=None,
        )

    def stream_response(self, *a, **k):
        raise NotImplementedError


class Bill(Model):
    async def get_response(self, *a, **k):
        return ModelResponse(
            output=[
                ResponseOutputMessage(
                    type="message",
                    id="msg_b",
                    role="assistant",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text",
                            text="Billing here; card 4111 1111 1111 1111 refunded.",
                            annotations=[],
                        )
                    ],
                )
            ],
            usage=Usage(),
            response_id=None,
        )

    def stream_response(self, *a, **k):
        raise NotImplementedError


billing = Agent(name="billing", instructions="Bill.", model=Bill())
triage = Agent(name="triage", instructions="Route.", handoffs=[billing], model=Triage())
res = Runner.run_sync(triage, "Refund my last charge.")
json.dump(res.to_input_list(), sys.stdout, indent=1, default=str)
