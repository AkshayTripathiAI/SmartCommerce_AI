"""Conversational shopping agent using Gemini or Ollama (OpenAI API)."""
import json
import logging
import re
from typing import Optional, List, Dict, Any
from uuid import UUID
import google.generativeai as genai
from google.generativeai.types import content_types
from openai import AsyncOpenAI

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.config import ai_settings
from app.core.kv import get_kv
from app.ai.tools import AgentTools, TOOL_DEFINITIONS

logger = logging.getLogger(__name__)

class ConversationMemory:
    """Conversation memory (Redis when configured, in-process otherwise)."""
    
    def __init__(self):
        self.max_history = 20  # Max messages to keep
    
    async def get_redis(self):
        return get_kv(decode_responses=True)
    
    def _trim(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keep the last messages, starting on a user turn so tool call/response pairs stay intact."""
        history = history[-self.max_history:]
        while history and history[0]["role"] != "user":
            history = history[1:]
        return history
    
    def _key(self, user_id: UUID) -> str:
        return f"chat:history:{user_id}"
    
    async def get_history(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get conversation history for user."""
        r = await self.get_redis()
        data = await r.get(self._key(user_id))
        if data:
            return json.loads(data)
        return []
    
    async def add_message(self, user_id: UUID, role: str, content: str):
        """Add a message to history."""
        # Normalize role
        if role == "assistant": role = "model"
        
        history = await self.get_history(user_id)
        history.append({"role": role, "parts": [content]})
        
        # Trim to max history
        if len(history) > self.max_history:
            history = self._trim(history)
        
        r = await self.get_redis()
        await r.setex(
            self._key(user_id),
            86400 * 7,  # 7 days TTL
            json.dumps(history)
        )
    
    async def add_function_call(self, user_id: UUID, name: str, args: dict, result: dict):
        """Add function call and result to history."""
        history = await self.get_history(user_id)
        
        # Add function call
        history.append({
            "role": "model",
            "parts": [{"function_call": {"name": name, "args": args}}]
        })
        
        # Add function response
        history.append({
            "role": "function",
            "parts": [{"function_response": {"name": name, "response": result}}]
        })
        
        if len(history) > self.max_history:
            history = self._trim(history)
        
        r = await self.get_redis()
        await r.setex(self._key(user_id), 86400 * 7, json.dumps(history))
    
    async def clear_history(self, user_id: UUID):
        """Clear conversation history for user."""
        r = await self.get_redis()
        await r.delete(self._key(user_id))
    
    async def close(self):
        """Nothing to close: the client is shared (see app.core.kv)."""


class ShoppingAgent:
    """Conversational shopping agent with tool calling."""
    
    SYSTEM_PROMPT = """You are 'Smarty', the helpful AI Shopping Assistant for SmartCommerce AI.

PERSONALITY:
- Friendly, upbeat, and professional. 🤖✨
- Use product names, never show technical UUID strings to users.

STRICT RULES:
1. **Tool Usage**: Use `search_products` first to find items and their IDs.
2. **UUIDs are Strings**: Every product has a `product_id`. This is a string (UUID) like "26f68cf0-...". 
   - ALWAYS copy the `id` from search results EXACTLY as a string.
   - NEVER try to convert it to an integer or guess it.
3. **Internal Logic**: NEVER mention "tools", "database", or "JSON". If a tool fails, say "I'm sorry, I couldn't find that product."
4. **Cart Management**: If a user asks to add something, ensure you have the `product_id` from a previous search result. If not, search for it first.

CORE CAPABILITIES:
- Search: `search_products`
- Details: `get_product_details`
- Cart: `view_cart`, `add_to_cart`
- Orders: `get_order_status`
- Policies: `lookup_policy`

IMPORTANT: Stay in character and never reveal technical details or internal reasoning."""

    def __init__(self, db: AsyncSession, user_id: UUID):
        self.db = db
        self.user_id = user_id
        self.tools = AgentTools(db, user_id)
        self.memory = ConversationMemory()
        self.provider = ai_settings.ai_provider
        
        if self.provider == "gemini":
            genai.configure(api_key=ai_settings.google_api_key)
            self.gemini_tools = self._create_gemini_tools()
            self.gemini_model = genai.GenerativeModel(
                model_name=ai_settings.chat_model,
                tools=self.gemini_tools,
                system_instruction=self.SYSTEM_PROMPT,
            )
        elif self.provider == "ollama":
            self.openai_client = AsyncOpenAI(
                base_url=ai_settings.ollama_base_url,
                api_key="ollama", # Required but unused
            )
            self.openai_tools = self._create_openai_tools()
    
    def _create_gemini_tools(self):
        """Convert tool definitions to Gemini function declarations."""
        functions = []
        for tool in TOOL_DEFINITIONS:
            functions.append(genai.protos.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: genai.protos.Schema(
                            type=self._get_gemini_type(v.get("type", "string")),
                            description=v.get("description", ""),
                        )
                        for k, v in tool.get("parameters", {}).get("properties", {}).items()
                    },
                    required=tool.get("parameters", {}).get("required", []),
                )
            ))
        return [genai.protos.Tool(function_declarations=functions)]
    
    def _get_gemini_type(self, type_str: str):
        type_map = {
            "string": genai.protos.Type.STRING,
            "number": genai.protos.Type.NUMBER,
            "integer": genai.protos.Type.INTEGER,
            "boolean": genai.protos.Type.BOOLEAN,
            "array": genai.protos.Type.ARRAY,
            "object": genai.protos.Type.OBJECT,
        }
        return type_map.get(type_str, genai.protos.Type.STRING)

    def _create_openai_tools(self):
        """Convert tool definitions to OpenAI tool format."""
        tools = []
        for tool in TOOL_DEFINITIONS:
            tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {})
                }
            })
        return tools
    
    async def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute a tool and return the result."""
        logger.debug(f"Executing tool: {name} with args: {args}")
        tool_method = getattr(self.tools, name, None)
        if not tool_method:
            return {"error": f"Unknown tool: {name}"}
        
        # Gemini returns all numbers as floats (e.g. quantity=1.0); integer DB columns need ints.
        args = {
            k: int(v) if isinstance(v, float) and v.is_integer() and k in ("quantity", "limit") else v
            for k, v in args.items()
        }

        try:
            # Special handling for missing product_id if model guessed wrong
            if name == "add_to_cart" and "product_id" not in args:
                return {"error": "Which product would you like to add? Please specify the name exactly."}
                
            result = await tool_method(**args)
            return result
        except Exception as e:
            return {"error": str(e)}

    async def chat(self, message: str) -> dict:
        """Process message using the configured provider."""
        if self.provider == "ollama":
            return await self._chat_ollama(message)
        else:
            return await self._chat_gemini(message)

    async def _chat_gemini(self, message: str) -> dict:
        import asyncio
        history = await self.memory.get_history(self.user_id)
        chat = self.gemini_model.start_chat(history=history)
        loop = asyncio.get_running_loop()
        tool_calls = []
        
        try:
            response = await loop.run_in_executor(None, lambda: chat.send_message(message))
            
            # Resolve tool calls (Gemini may request several in parallel); cap the rounds.
            for _ in range(5):
                parts = response.candidates[0].content.parts if response.candidates else []
                calls = [p.function_call for p in parts if getattr(p, "function_call", None) and p.function_call.name]
                if not calls:
                    break
                
                response_parts = []
                for fc in calls:
                    args = dict(fc.args) if fc.args else {}
                    result = await self._execute_tool(fc.name, args)
                    tool_calls.append({"name": fc.name, "args": args, "result": result})
                    response_parts.append(genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=fc.name, response={"result": result}
                        )
                    ))
                
                response = await loop.run_in_executor(
                    None,
                    lambda rp=response_parts: chat.send_message(genai.protos.Content(parts=rp)),
                )
            
            final_text = ""
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        final_text += part.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            return {
                "response": "I'm sorry, I'm having a bit of trouble connecting right now. Please try again in a moment. 🔄",
                "tool_calls": tool_calls or None,
            }
        
        if not final_text:
            final_text = "I'm sorry, I couldn't come up with an answer for that. Could you rephrase?"
        
        # Persist the turn only after it succeeded, so a failed call never leaves a dangling message.
        # Only text turns are replayed as history; tool context lives within a single turn.
        await self.memory.add_message(self.user_id, "user", message)
        await self.memory.add_message(self.user_id, "model", final_text)
        
        return {
            "response": final_text,
            "tool_calls": tool_calls if tool_calls else None,
        }

    async def _chat_ollama(self, message: str) -> dict:
        history = await self.memory.get_history(self.user_id)
        
        # Convert history format for OpenAI correctly
        openai_history = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        for idx, msg in enumerate(history):
            if msg["role"] == "user":
                openai_history.append({"role": "user", "content": "".join([p for p in msg["parts"] if isinstance(p, str)])})
            elif msg["role"] == "model":
                parts = msg["parts"]
                text_content = ""
                fc_id = f"call_{idx}"
                has_fc = False
                for p in parts:
                    if isinstance(p, str):
                        text_content += p
                    elif isinstance(p, dict) and "function_call" in p:
                        has_fc = True
                        fc = p["function_call"]
                        openai_history.append({
                            "role": "assistant",
                            "content": text_content if text_content else None,
                            "tool_calls": [{
                                "id": fc_id,
                                "type": "function",
                                "function": {
                                    "name": fc["name"],
                                    "arguments": json.dumps(fc["args"])
                                }
                            }]
                        })
                        # Find corresponding function response
                        if idx + 1 < len(history) and history[idx+1]["role"] == "function":
                            resp = history[idx+1]["parts"][0].get("function_response", {})
                            openai_history.append({
                                "role": "tool",
                                "tool_call_id": fc_id,
                                "name": fc["name"],
                                "content": json.dumps(resp.get("response", {}))
                            })
                if not has_fc:
                    openai_history.append({"role": "assistant", "content": text_content})
            
        openai_history.append({"role": "user", "content": message})
        logger.debug(f"Ollama History: {json.dumps(openai_history, indent=2)}")
        
        tool_calls_result = []
        current_messages = openai_history
        
        for _ in range(5):
            try:
                logger.debug(f"Calling Ollama with {len(current_messages)} messages...")
                response = await self.openai_client.chat.completions.create(
                    model=ai_settings.ollama_model,
                    messages=current_messages,
                    tools=self.openai_tools,
                )
            except Exception as e:
                logger.error(f"Ollama API Error: {e}", exc_info=True)
                return {"response": "I'm sorry, I'm having a bit of trouble connecting right now. 🔄", "tool_calls": None}
            
            message_response = response.choices[0].message
            content = message_response.content or ""
            
            # Robust tool call detection (handle both SDK objects and fallback dicts)
            tool_calls = message_response.tool_calls
            
            # Fallback for models that output JSON text instead of native tool_calls
            if not tool_calls and "{" in content and "name" in content:
                try:
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        guessed_call = json.loads(json_match.group())
                        name = guessed_call.get("name") or guessed_call.get("function")
                        args = guessed_call.get("parameters") or guessed_call.get("args") or {}
                        
                        if name in [t["name"] for t in TOOL_DEFINITIONS]:
                            # Hide the raw JSON from the user if it was a tool call
                            id = f"fallback_{_}"
                            tool_calls = [{
                                "id": id,
                                "type": "function",
                                "function": {"name": name, "arguments": json.dumps(args)}
                            }]
                            # Optionally strip the JSON from content if we use it
                            content = content.replace(json_match.group(), "").strip()
                except:
                    pass

            if tool_calls:
                # Store message_response for next turn (ensure it has tool_calls if fallback was used)
                message_response.tool_calls = tool_calls
                current_messages.append(message_response)
                
                for tc in tool_calls:
                    # Generic access for both object and dict
                    if isinstance(tc, dict):
                        f_name = tc["function"]["name"]
                        f_args_str = tc["function"]["arguments"]
                        tc_id = tc["id"]
                    else:
                        f_name = tc.function.name
                        f_args_str = tc.function.arguments
                        tc_id = tc.id
                        
                    f_args = json.loads(f_args_str)
                    
                    result = await self._execute_tool(f_name, f_args)
                    tool_calls_result.append({
                        "name": f_name,
                        "args": f_args,
                        "result": result
                    })
                    
                    await self.memory.add_function_call(self.user_id, f_name, f_args, result)
                    
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": f_name,
                        "content": json.dumps(result)
                    })
            else:
                # Final response turn
                await self.memory.add_message(self.user_id, "user", message)
                await self.memory.add_message(self.user_id, "model", content)
                return {
                    "response": content,
                    "tool_calls": tool_calls_result if tool_calls_result else None
                }
        
        return {"response": "I'm sorry, I'm having trouble thinking clearly right now. Let's try again!", "tool_calls": None}

    async def clear_conversation(self):
        """Clear conversation history."""
        await self.memory.clear_history(self.user_id)

conversation_memory = ConversationMemory()
