"""Tests for the generalization ladders module."""

import json
import pytest
from typing import Any

from pgm.config import MemoryCategory, LadderSource
from pgm.ladders.ontology import OntologyRegistry
from pgm.ladders.llm_proposer import LLMProposer
from pgm.ladders.verifier import RungVerifier
from pgm.ladders.builder import LadderBuilder
from pgm.llm import MockLLMClient
from pgm.models import ExtractedMemory


class TestOntologyAdapters:
    def test_location_adapter_match(self) -> None:
        registry = OntologyRegistry()
        proposals = registry.propose_all("Pune", MemoryCategory.LOCATION, "city")
        assert len(proposals) == 2
        assert proposals[0].level == 1
        assert proposals[0].text == "Maharashtra"
        assert proposals[0].source == LadderSource.ONTOLOGY

    def test_employment_adapter_match(self) -> None:
        registry = OntologyRegistry()
        proposals = registry.propose_all("Tesla", MemoryCategory.EMPLOYMENT, "employer")
        assert len(proposals) == 2
        assert proposals[0].level == 1
        assert proposals[0].text == "Automotive Company"

    def test_ontology_miss(self) -> None:
        registry = OntologyRegistry()
        proposals = registry.propose_all("Unknown City", MemoryCategory.LOCATION, "city")
        assert len(proposals) == 0


class TestLLMProposer:
    @pytest.mark.asyncio
    async def test_proposer_parses_json(self) -> None:
        llm = MockLLMClient([
            json.dumps({
                "ladder": [
                    {"level": 1, "text": "Maharashtra"},
                    {"level": 2, "text": "India"},
                    {"level": 3, "text": "Asia"}
                ]
            })
        ])
        proposer = LLMProposer(llm)
        proposals = await proposer.propose("Pune", MemoryCategory.LOCATION, "city")
        
        assert len(proposals) == 3
        assert proposals[0].level == 1
        assert proposals[0].text == "Maharashtra"
        assert proposals[0].source == LadderSource.LLM

    @pytest.mark.asyncio
    async def test_proposer_handles_bad_json(self) -> None:
        llm = MockLLMClient(["Invalid JSON"])
        proposer = LLMProposer(llm)
        proposals = await proposer.propose("Pune", MemoryCategory.LOCATION, "city")
        assert len(proposals) == 0


class TestRungVerifier:
    @pytest.mark.asyncio
    async def test_verifier_all_true(self) -> None:
        llm = MockLLMClient([
            json.dumps({
                "entails": True,
                "monotonic": True,
                "no_leakage": True,
                "reasoning": "Looks good."
            })
        ])
        verifier = RungVerifier(llm)
        result = await verifier.verify("Pune", "Maharashtra")
        
        assert result.is_valid
        assert result.entails
        assert result.monotonic
        assert result.no_leakage

    @pytest.mark.asyncio
    async def test_verifier_fails_if_leakage(self) -> None:
        llm = MockLLMClient([
            json.dumps({
                "entails": True,
                "monotonic": True,
                "no_leakage": False,
                "reasoning": "Leaked CEO."
            })
        ])
        verifier = RungVerifier(llm)
        result = await verifier.verify("Elon Musk", "CEO of Tesla")
        
        assert not result.is_valid


class TestLadderBuilder:
    @pytest.mark.asyncio
    async def test_builder_uses_ontology_first(self, repository: Any, session: Any, user_id: str) -> None:
        llm = MockLLMClient()
        builder = LadderBuilder(
            llm_client=llm,
            repository=repository,
            ontology_registry=OntologyRegistry(),
            verifier=RungVerifier(MockLLMClient([
                json.dumps({"entails": True, "monotonic": True, "no_leakage": True}),
                json.dumps({"entails": True, "monotonic": True, "no_leakage": True}),
            ]))
        )
        
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()
        
        rungs = await builder.build_ladder_for_memory(memory)
        assert len(rungs) == 2
        assert rungs[0].text == "Maharashtra"
        assert rungs[1].text == "India"
        assert rungs[0].source == LadderSource.ONTOLOGY.value
        assert len(llm.call_log) == 0  # Proposer LLM shouldn't be called

    @pytest.mark.asyncio
    async def test_builder_falls_back_to_llm(self, repository: Any, session: Any, user_id: str) -> None:
        proposer_llm = MockLLMClient([
            json.dumps({
                "ladder": [
                    {"level": 1, "text": "Software Framework"},
                    {"level": 2, "text": "Software"}
                ]
            })
        ])
        verifier_llm = MockLLMClient([
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}),
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}),
        ])
        
        builder = LadderBuilder(
            llm_client=proposer_llm,
            repository=repository,
            ontology_registry=OntologyRegistry(),
            proposer=LLMProposer(proposer_llm),
            verifier=RungVerifier(verifier_llm)
        )
        
        mem = ExtractedMemory(
            category=MemoryCategory.PREFERENCES,
            slot_key="tech",
            value="React",
            confidence=0.9
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()
        
        rungs = await builder.build_ladder_for_memory(memory)
        assert len(rungs) == 2
        assert rungs[0].text == "Software Framework"
        assert rungs[0].source == LadderSource.LLM.value
        assert len(proposer_llm.call_log) == 1

    @pytest.mark.asyncio
    async def test_builder_stops_on_verification_failure(self, repository: Any, session: Any, user_id: str) -> None:
        verifier_llm = MockLLMClient([
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}),  # L1 passes
            json.dumps({"entails": False, "monotonic": True, "no_leakage": True}), # L2 fails
        ])
        
        builder = LadderBuilder(
            llm_client=MockLLMClient(),
            repository=repository,
            ontology_registry=OntologyRegistry(),
            verifier=RungVerifier(verifier_llm)
        )
        
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()
        
        # Ontology returns [Maharashtra, India]
        # L1 (Maharashtra) passes, L2 (India) is forced to fail by mock
        rungs = await builder.build_ladder_for_memory(memory)
        
        # Should only have inserted L1
        assert len(rungs) == 1
        assert rungs[0].level == 1
        assert rungs[0].text == "Maharashtra"
