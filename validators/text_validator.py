
import math
import torch
import wandb
import random
import asyncio
import template.reward
import bittensor as bt

from base_validator import BaseValidator
from template.protocol import StreamPrompting
from template.utils import call_openai, get_question


class TextValidator(BaseValidator):
    def __init__(self, dendrite, config, subtensor, wallet):
        super().__init__(dendrite, config, subtensor, wallet, timeout=60)
        self.streaming = True
        self.query_type = "text"
        self.model = "gpt-4-1106-preview"
        self.weight = 1
        self.seed = 1234

        self.wandb_data = {
            "modality": "text",
            "prompts": {},
            "responses": {},
            "scores": {},
            "timestamps": {},
        }

    async def start_query(self, metagraph, available_uids=None, messages_dict=None):
        # example messages_dict = {36: [{'role': 'user', 'content': "who are you"}]}
        # Set available_uids to keys of messages if available_uids is not provided
        if available_uids is None:
            if messages_dict is not None:
                available_uids = list(messages_dict.keys())
            else:
                raise ValueError("Either available_uids or messages must be provided.")

        query_tasks = []
        uid_to_question = {}

        # Check and set messages for each UID
        for uid in available_uids:
            # Use existing message if available, otherwise generate a new one
            if messages_dict is not None and uid in messages_dict:
                message = messages_dict[uid]
            else:
                prompt = await get_question("text", len(available_uids))
                message = [{'role': 'user', 'content': prompt}]

            uid_to_question[uid] = message
            syn = StreamPrompting(messages=message, model=self.model, seed=self.seed)
            bt.logging.info(f"Sending {syn.model} {self.query_type} request to uid: {uid}, timeout {self.timeout}: {message[0]['content']}")
            task = self.query_miner(metagraph.axons[uid], uid, syn)
            query_tasks.append(task)
            self.wandb_data["prompts"][uid] = message

        query_responses = await asyncio.gather(*query_tasks)
        return query_responses, uid_to_question

    async def handle_response(self, uid, responses):
        full_response = ""
        for resp in responses:
            async for chunk in resp:
                if isinstance(chunk, str):
                    bt.logging.trace(chunk)
                    full_response += chunk
            bt.logging.debug(f"full_response for uid {uid}: {full_response}")
            break
        return uid, full_response

    async def score_responses(self, query_responses, uid_to_question, metagraph):
        scores = torch.zeros(len(metagraph.hotkeys))
        uid_scores_dict = {}
        openai_response_tasks = []

        # Decide to score all UIDs this round based on a chance
        random_number = random.random()
        will_score_all = random_number < 1/11
        bt.logging.info(f"Random Number: {random_number}, Will score text responses: {will_score_all}")

        for uid, response in query_responses:
            self.wandb_data["responses"][uid] = response
            if will_score_all and response:
                messages = uid_to_question[uid]
                task = call_openai(messages, 0, self.model, self.seed)
                openai_response_tasks.append((uid, task))

        openai_responses = await asyncio.gather(*[task for _, task in openai_response_tasks])

        scoring_tasks = []
        for (uid, _), openai_answer in zip(openai_response_tasks, openai_responses):
            if openai_answer:
                response = next(res for u, res in query_responses if u == uid)  # Find the matching response
                task = template.reward.openai_score(openai_answer, response, self.weight)
                scoring_tasks.append((uid, task))

        scored_responses = await asyncio.gather(*[task for _, task in scoring_tasks])

        for (uid, _), scored_response in zip(scoring_tasks, scored_responses):
            if scored_response is not None:
                scores[uid] = scored_response
                uid_scores_dict[uid] = scored_response
            else:
                scores[uid] = 0
                uid_scores_dict[uid] = 0
            # self.wandb_data["scores"][uid] = score

        if uid_scores_dict != {}:
            bt.logging.info(f"text_scores is {uid_scores_dict}")
        return scores, uid_scores_dict, self.wandb_data

    async def get_and_score(self, metagraph, available_uids=None, messages_dict=None):
        query_responses, uid_to_question = await self.start_query(metagraph, available_uids, messages_dict)
        return await self.score_responses(query_responses, uid_to_question, metagraph)