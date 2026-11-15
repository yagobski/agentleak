# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Produce a real OpenAI Agents SDK to_input_list() offline with a scripted model."""

import json
import sys

from agents import Agent, Model, ModelResponse, Runner, Usage, function_tool, set_tracing_disabled
from openai.types.responses import (
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

set_tracing_disabled(True)


@function_tool
def lookup_customer(customer_id: str) -> str:
    """Look up a customer record."""
    return "Customer Dana Example, email dana.example@example.com, phone 555-0142, SSN 412-55-9087"


@function_tool
def send_crm_note(note: str) -> str:
    """Write a note to the CRM."""
    return "ok"


class Scripted(Model):
    def __init__(self):
        self.turn = 0

    async def get_response(self, *a, **k):
        self.turn += 1
        if self.turn == 1:
            out = [
                ResponseFunctionToolCall(
                    type="function_call",
                    id="fc_1",
                    call_id="call_1",
                    name="lookup_customer",
                    arguments='{"customer_id":"C-1"}',
                    status="completed",
                )
            ]
        elif self.turn == 2:
            out = [
                ResponseFunctionToolCall(
                    type="function_call",
                    id="fc_2",
                    call_id="call_2",
                    name="send_crm_note",
                    arguments='{"note":"Called dana.example@example.com about SSN 412-55-9087"}',
                    status="completed",
                )
            ]
        else:
            out = [
                ResponseOutputMessage(
                    type="message",
                    id="msg_1",
                    role="assistant",
                    status="completed",
                    content=[
                        ResponseOutputText(
                            type="output_text", text="Done, the note is saved.", annotations=[]
                        )
                    ],
                )
            ]
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    def stream_response(self, *a, **k):
        raise NotImplementedError


agent = Agent(
    name="support", instructions="Help.", tools=[lookup_customer, send_crm_note], model=Scripted()
)
res = Runner.run_sync(agent, "Please add a CRM note for customer C-1.")
json.dump(res.to_input_list(), sys.stdout, indent=1, default=str)
