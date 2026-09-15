"""
Mock LLM provider — used when no OPENAI_API_KEY is configured.

It returns canned fixtures for each stage so the pipeline can run
end-to-end and produce a real (but pre-written) documentary video.

This is NOT a stub that returns empty strings; each method returns a
well-formed JSON object that satisfies the corresponding Pydantic schema.
That makes the mock useful both as a demo mode and as the golden fixture
for tests.
"""
from __future__ import annotations

import json
import re

from app.providers.base import LLMProvider, LLMRequest, LLMResponse

# --------------------------------------------------------------------------
# Research Package fixture (new rich schema — returned by Research Engine steps)
# --------------------------------------------------------------------------

MOCK_RESEARCH_PACKAGE = {
    "metadata": {
        "version": "1.0",
        "topic": "How Did Ancient Humans Survive Deadly Winters?",
        "created_at": "2024-01-01T00:00:00Z",
        "duration_sec": 12.5,
        "job_id": "test-job-001",
        "quality_score": 0.72,
        "quality_warnings": [],
        "source_count": 8,
        "claim_count": 10,
    },
    "research_questions": [
        {"id": "RQ-001", "text": "How did Neanderthals adapt to cold climates?", "question_type": "causal", "importance_score": 0.9, "status": "active", "parent_id": None, "sources_touched": [], "claims_touched": []},
        {"id": "RQ-002", "text": "What role did fire play in Ice Age survival?", "question_type": "evidence", "importance_score": 0.95, "status": "active", "parent_id": None, "sources_touched": [], "claims_touched": []},
        {"id": "RQ-003", "text": "What clothing and shelter technologies existed?", "question_type": "evidence", "importance_score": 0.85, "status": "active", "parent_id": None, "sources_touched": [], "claims_touched": []},
        {"id": "RQ-004", "text": "How did Ice Age humans acquire food in winter?", "question_type": "causal", "importance_score": 0.9, "status": "active", "parent_id": None, "sources_touched": [], "claims_touched": []},
        {"id": "RQ-005", "text": "What is the evidence for these survival strategies?", "question_type": "evidence", "importance_score": 0.8, "status": "active", "parent_id": None, "sources_touched": [], "claims_touched": []},
    ],
    "sources": [
        {"id": "SRC-00000001", "url": "https://www.nature.com/articles/s41586-019-1290-4", "title": "The evolutionary history of cold adaptation in humans", "tier": "TIER1", "authority": 0.95, "recency": 0.7, "methodology": 0.95, "relevance": 0.9, "citation_quality": 0.95, "independence": 1.0, "overall_score": 0.92, "score_reason": "Peer-reviewed Nature article", "content_hash": "", "snippet": "Ancient humans developed several cold-adapted physiological traits over the course of the Pleistocene.", "published_date": "2019-06-01", "author": "Research Team", "domain": "nature.com", "lineage": {"original_url": "", "intermediate_urls": [], "is_independent": True}, "reviewed": False, "approved": True, "claims_from_this_source": []},
        {"id": "SRC-00000002", "url": "https://en.wikipedia.org/wiki/Neanderthal", "title": "Neanderthal - Wikipedia", "tier": "TIER3", "authority": 0.5, "recency": 0.6, "methodology": 0.3, "relevance": 0.8, "citation_quality": 0.4, "independence": 0.8, "overall_score": 0.52, "score_reason": "Wikipedia: useful for discovery", "content_hash": "", "snippet": "Neanderthals inhabited Eurasia from the Pleistocene to approximately 40,000 years ago.", "published_date": "", "author": "", "domain": "wikipedia.org", "lineage": {"original_url": "", "intermediate_urls": [], "is_independent": True}, "reviewed": False, "approved": True, "claims_from_this_source": []},
        {"id": "SRC-00000003", "url": "https://www.smithsonianmag.com/science-nature/how-neanderthals-adapted-to-cold-180971856/", "title": "How Neanderthals Adapted to Cold - Smithsonian", "tier": "TIER2", "authority": 0.85, "recency": 0.7, "methodology": 0.7, "relevance": 0.9, "citation_quality": 0.8, "independence": 0.9, "overall_score": 0.82, "score_reason": "Established science publication", "content_hash": "", "snippet": "New research reveals how Neanderthal anatomy and behavior helped them survive European winters.", "published_date": "2021-03-15", "author": "", "domain": "smithsonianmag.com", "lineage": {"original_url": "", "intermediate_urls": [], "is_independent": True}, "reviewed": False, "approved": True, "claims_from_this_source": []},
    ],
    "claims": [
        {"claim_id": "CLM-001", "text": "Neanderthals lived through glacial winters in Europe for over 200,000 years.", "claim_type": "historical", "importance": "high", "confidence": 0.9, "certainty_level": "STRONG_EVIDENCE", "certainty_reason": "Supported by multiple independent sources", "status": "supported", "uncertainty": "", "notes": "", "source_ids": ["SRC-00000001", "SRC-00000002"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-002", "text": "The controlled use of fire dates back at least 400,000 years.", "claim_type": "archaeological", "importance": "high", "confidence": 0.92, "certainty_level": "STRONG_EVIDENCE", "certainty_reason": "Archaeological hearths at multiple sites", "status": "supported", "uncertainty": "", "notes": "", "source_ids": ["SRC-00000001"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-003", "text": "Mammoth-bone huts have been excavated in Ukraine and Russia.", "claim_type": "archaeological", "importance": "high", "confidence": 0.88, "certainty_level": "STRONG_EVIDENCE", "certainty_reason": "Physical archaeological evidence", "status": "supported", "uncertainty": "", "notes": "", "source_ids": ["SRC-00000003"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-004", "text": "Tailored clothing, evidenced by bone awls, appeared at least 70,000 years ago.", "claim_type": "technological", "importance": "medium", "confidence": 0.75, "certainty_level": "PLAUSIBLE_INTERPRETATION", "certainty_reason": "Bone awls found but functional use inferred", "status": "supported", "uncertainty": "Hard to prove awls were used specifically for clothing", "notes": "", "source_ids": ["SRC-00000002"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-005", "text": "Ice Age humans hunted megafauna for both food and warm hides.", "claim_type": "behavioral", "importance": "high", "confidence": 0.85, "certainty_level": "STRONG_EVIDENCE", "certainty_reason": "Isotopic evidence and tool marks on bones", "status": "supported", "uncertainty": "", "notes": "", "source_ids": ["SRC-00000001", "SRC-00000003"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-006", "text": "Fat consumption from megafauna was critical for surviving extreme cold.", "claim_type": "biological", "importance": "high", "confidence": 0.82, "certainty_level": "PLAUSIBLE_INTERPRETATION", "certainty_reason": "Logical inference from available evidence", "status": "supported", "uncertainty": "Cannot directly measure ancient dietary fat intake", "notes": "", "source_ids": ["SRC-00000001"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
        {"claim_id": "CLM-007", "text": "Neanderthal body shape was genetically selected for cold adaptation.", "claim_type": "biological", "importance": "medium", "confidence": 0.6, "certainty_level": "PLAUSIBLE_INTERPRETATION", "certainty_reason": "Body proportions consistent with cold adaptation but causality debated", "status": "unresolved", "uncertainty": "Selection vs. neutral drift debated", "notes": "", "source_ids": ["SRC-00000001", "SRC-00000003"], "contradictory_claim_ids": [], "visual_opportunity_id": None, "story_opportunity_id": None},
    ],
    "claim_source_links": [
        {"claim_id": "CLM-001", "source_id": "SRC-00000001", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-001", "source_id": "SRC-00000002", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-002", "source_id": "SRC-00000001", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-003", "source_id": "SRC-00000003", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-004", "source_id": "SRC-00000002", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-005", "source_id": "SRC-00000001", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-005", "source_id": "SRC-00000003", "relationship": "supports", "notes": ""},
        {"claim_id": "CLM-006", "source_id": "SRC-00000001", "relationship": "supports", "notes": ""},
    ],
    "contradictions": [
        {"id": "CTR-001", "claim_id_a": "CLM-007", "claim_id_b": "CLM-002", "position_a": "Neanderthal body shape was genetically selected for cold adaptation", "position_b": "Behavioral adaptations like fire were the primary survival mechanism", "possible_reason": "These represent different relative emphasis in the literature", "resolution": "partial", "resolution_notes": "Both genetic adaptation and behavioral adaptation likely played roles"}
    ],
    "research_gaps": [
        {"id": "GAP-001", "question": "How did infants and elderly survive Ice Age winters?", "status": "insufficient_evidence", "reason": "Limited archaeological evidence for vulnerable age groups", "related_question_ids": ["RQ-001", "RQ-003"]},
        {"id": "GAP-002", "question": "What role did social cooperation play in survival?", "status": "insufficient_evidence", "reason": "Cooperation is hypothesized but difficult to archaeologically verify", "related_question_ids": ["RQ-004"]}
    ],
    "timeline": [
        {"period": "Pleistocene", "start_date": "~2.58 million years ago", "end_date": "~11,700 years ago", "events": ["Neanderthals inhabited Europe and Asia"], "uncertainty": "Dates are approximate", "is_approximate": True},
        {"period": "Late Pleistocene", "start_date": "~130,000 years ago", "end_date": "~40,000 years ago", "events": ["Peak Neanderthal populations", "Evidence of sophisticated tool use", "Controlled fire use"], "uncertainty": "", "is_approximate": True}
    ],
    "geography": [
        {"name": "European Ice Sheet margins", "region": "Europe", "country": "Multiple", "latitude": 50.0, "longitude": 10.0, "period": "Late Pleistocene", "evidence": "Archaeological sites with hearths and tools"},
        {"name": "Simbioskaya, Ukraine", "region": "Eastern Europe", "country": "Ukraine", "latitude": 48.0, "longitude": 32.0, "period": "~15,000 BCE", "evidence": "Mammoth-bone hut foundations"}
    ],
    "quantitative_facts": [
        {"id": "QF-001", "value": 400000, "unit": "years ago", "context": "Earliest evidence for controlled fire use", "minimum": None, "maximum": None, "approximate": True, "uncertainty": "Evidence contested at earliest sites", "source_ids": ["SRC-00000001"]},
        {"id": "QF-002", "value": 20, "unit": "degrees Celsius", "context": "Temperature difference between glacial and interglacial periods", "minimum": 15, "maximum": 25, "approximate": False, "uncertainty": "", "source_ids": ["SRC-00000001"]}
    ],
    "visual_opportunities": [
        {"id": "VO-001", "claim_id": "CLM-002", "opportunity_type": "environment", "description": "A reconstructed cave hearth with fire and human figures", "visual_spec": "Interior of a cave, warm orange firelight on cave walls, two stick figures in fur cloaks warming by fire", "environment_hint": "cave_interior", "mood_hint": "warm"}
    ],
    "story_opportunities": [
        {"id": "SO-001", "hook_candidates": ["A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive?"], "surprising_facts": ["Mammoth bones were used as building materials", "Fat was more valuable than meat for survival"], "contradictions": ["Were Neanderthals adapted to cold genetically or behaviorally?"], "escalations": ["As the Ice Age deepened, survival became harder and harder"], "emotional_beats": ["The moment fire was first controlled changed human history forever"], "questions": ["What would you do to survive?"], "final_takeaways": ["Survival required cooperation, creativity, and the courage to adapt."]}
    ],
    "synthesis": {
        "central_question": "How did ancient humans survive deadly Ice Age winters?",
        "short_answer": "Ancient humans survived Ice Age winters by combining fire, tailored clothing, cooperative shelter, and high-fat megafauna hunting into a flexible survival system.",
        "detailed_answer": "Ancient humans survived deadly Ice Age winters through a combination of physiological adaptations and sophisticated behavioral strategies. Neanderthals and early modern humans inhabited Eurasia during glacial periods, facing temperatures that could drop far below freezing. The controlled use of fire, evidenced by hearths dating back at least 400,000 years, provided warmth, light, and the ability to cook food that would otherwise be inedible.",
        "strongest_evidence": ["Controlled fire use dated to 400,000 years ago at multiple sites", "Mammoth-bone hut archaeological sites excavated in Ukraine and Russia"],
        "weakest_evidence": ["Genetic vs. behavioral adaptation in Neanderthal cold tolerance"],
        "major_uncertainties": ["How did vulnerable populations (infants, elderly) survive?"],
        "major_disagreements": ["Were Neanderthal cold adaptations primarily genetic or behavioral?"],
        "timeline_summary": ["~400,000 years ago: Earliest controlled fire evidence", "~70,000 years ago: Bone awls suggesting tailored clothing"],
        "important_examples": ["Mammoth-bone hut at Simbioskaya, Ukraine", "Hearth sites in European caves"],
        "counterintuitive_findings": ["Fat was more valuable than meat in extreme cold", "Sharing warmth in a small space was more important than fire alone"]
    },
    "quality_score": {
        "source_quality": 0.75,
        "coverage": 0.85,
        "claim_traceability": 0.9,
        "independence": 0.88,
        "contradiction_detection": 0.7,
        "uncertainty_handling": 0.8,
        "research_depth": 0.72,
        "visual_value": 0.85,
        "story_value": 0.9,
        "overall_score": 0.79
    }
}


# --------------------------------------------------------------------------
# Story Package fixture (Story Intelligence Engine)
# --------------------------------------------------------------------------

MOCK_STORY_PACKAGE = {
    "metadata": {
        "version": "1",
        "story_package_id": "SP-001",
        "research_package_id": "test-job-001",
        "research_package_hash": "a1b2c3d4e5f67890",
        "topic": "How Did Ancient Humans Survive Deadly Winters?",
        "job_id": "test-job-001",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
        "status": "in_progress",
        "review_status": "draft",
        "research_quality_passed": True,
        "research_quality_overall": 0.79,
        "research_failures": [],
        "research_warnings": [],
    },
    "research_status": "complete",
    "research_failures": [],
    "research_warnings": [],
    "thesis": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "abc123",
        },
        "candidates": [
            {
                "thesis_id": "THS-001",
                "statement": (
                    "Ancient humans survived deadly Ice Age winters not through any single "
                    "invention, but by combining controlled fire, tailored clothing, "
                    "cooperative shelter, and high-fat megafauna hunting into an integrated "
                    "survival system that required constant group cooperation."
                ),
                "supporting_claim_ids": ["CLM-001", "CLM-002", "CLM-003", "CLM-005", "CLM-006"],
                "contradicting_claim_ids": ["CLM-007"],
                "uncertainty": "Relative importance of genetic vs. behavioral adaptations is debated.",
                "explanatory_power": 0.92,
                "novelty": 0.6,
                "story_value": 0.9,
                "visual_value": 0.85,
                "audience_relevance": 0.95,
                "evidence_strength": 0.88,
                "overall_score": 0.87,
                "reason": "Covers all major survival strategies and has strong visual potential.",
            },
            {
                "thesis_id": "THS-002",
                "statement": (
                    "The discovery and controlled use of fire was the pivotal breakthrough "
                    "that enabled humans to survive glacial winters, fundamentally changing "
                    "their relationship with the environment."
                ),
                "supporting_claim_ids": ["CLM-002"],
                "contradicting_claim_ids": [],
                "uncertainty": "",
                "explanatory_power": 0.7,
                "novelty": 0.5,
                "story_value": 0.75,
                "visual_value": 0.8,
                "audience_relevance": 0.9,
                "evidence_strength": 0.92,
                "overall_score": 0.78,
                "reason": "Strong evidence but narrower scope than THS-001.",
            },
            {
                "thesis_id": "THS-003",
                "statement": (
                    "Social cooperation and group cohesion were the ultimate survival "
                    "advantage that allowed Ice Age humans to outlast extreme seasonal "
                    "challenges that would have killed any individual acting alone."
                ),
                "supporting_claim_ids": ["CLM-001", "CLM-005"],
                "contradicting_claim_ids": [],
                "uncertainty": "Cooperation is hypothesized but difficult to archaeologically verify.",
                "explanatory_power": 0.8,
                "novelty": 0.75,
                "story_value": 0.95,
                "visual_value": 0.7,
                "audience_relevance": 0.85,
                "evidence_strength": 0.65,
                "overall_score": 0.8,
                "reason": "Strong narrative hook but softer archaeological evidence.",
            },
        ],
        "selected_id": "THS-001",
        "review_status": "draft",
        "review_notes": "",
    },
    "angle": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "def456",
        },
        "candidates": [
            {
                "angle_id": "ANG-001",
                "type": "survival",
                "title": "The Survival Formula: Fire, Fur, Fat, and Together",
                "description": (
                    "Walk through the four pillars of Ice Age survival — fire, clothing, "
                    "shelter, and food — and reveal how none of them worked alone. Each "
                    "pillar reinforces the others, building to a thesis about cooperation."
                ),
                "central_tension": (
                    "Could any single invention have worked without the others? "
                    "What made the combination so powerful?"
                ),
                "supporting_claim_ids": ["CLM-001", "CLM-002", "CLM-003", "CLM-005", "CLM-006"],
                "uncertainties": ["How much did genetic cold adaptation contribute?"],
                "visual_potential": 0.9,
                "curiosity": 0.85,
                "emotional_potential": 0.8,
                "story_strength": 0.92,
                "overall_score": 0.88,
            },
            {
                "angle_id": "ANG-002",
                "type": "contradiction",
                "title": "What Neanderthals Knew About Cold That Modern Science Is Still Debating",
                "description": (
                    "Open with a paradox: Neanderthals thrived through ice ages, yet we "
                    "still don't fully agree on whether it was their bodies or their "
                    "behaviors that made the difference. The contradiction drives curiosity."
                ),
                "central_tension": (
                    "Were Neanderthals built for cold, or did they simply learn to "
                    "master it through behavior and culture?"
                ),
                "supporting_claim_ids": ["CLM-001", "CLM-007"],
                "uncertainties": ["Genetic adaptation vs. behavioral adaptation is unresolved."],
                "visual_potential": 0.75,
                "curiosity": 0.95,
                "emotional_potential": 0.85,
                "story_strength": 0.8,
                "overall_score": 0.85,
            },
            {
                "angle_id": "ANG-003",
                "type": "transformation",
                "title": "The Transformation That Changed Everything: How Fire Made Us Human",
                "description": (
                    "Track the transformation of early humans from cold-exposed survivors "
                    "to masters of the winter environment through the discovery of fire. "
                    "The transformation arc runs from vulnerability to triumph."
                ),
                "central_tension": (
                    "What would have happened to our ancestors without fire? "
                    "The transformation seems inevitable in hindsight — but it wasn't."
                ),
                "supporting_claim_ids": ["CLM-002", "CLM-003", "CLM-004"],
                "uncertainties": [],
                "visual_potential": 0.85,
                "curiosity": 0.8,
                "emotional_potential": 0.9,
                "story_strength": 0.87,
                "overall_score": 0.86,
            },
        ],
        "selected_id": "ANG-001",
        "review_status": "draft",
        "review_notes": "",
    },
    "title": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "ghi789",
        },
        "candidates": [
            {"title_id": "TTL-001", "title": "How Did Ancient Humans Survive Deadly Winters?", "curiosity_score": 0.9, "clarity_score": 0.95, "specificity_score": 0.85, "novelty_score": 0.6, "truthfulness_score": 1.0, "thesis_alignment": 0.9, "payoff_alignment": 0.85, "mobile_readability": 0.95, "overall_score": 0.87, "risk_flags": [], "promised_question": "How did they survive?", "promised_payoff": "A clear survival formula."},
            {"title_id": "TTL-002", "title": "The Ice Age Trick That Kept Humans Alive", "curiosity_score": 0.95, "clarity_score": 0.85, "specificity_score": 0.7, "novelty_score": 0.7, "truthfulness_score": 0.95, "thesis_alignment": 0.85, "payoff_alignment": 0.8, "mobile_readability": 0.9, "overall_score": 0.85, "risk_flags": [], "promised_question": "What was the trick?", "promised_payoff": "A specific survival technique revealed."},
            {"title_id": "TTL-003", "title": "Why You Wouldn't Last One Night in an Ice Age Cave", "curiosity_score": 1.0, "clarity_score": 0.9, "specificity_score": 0.8, "novelty_score": 0.75, "truthfulness_score": 0.95, "thesis_alignment": 0.7, "payoff_alignment": 0.75, "mobile_readability": 0.85, "overall_score": 0.84, "risk_flags": [], "promised_question": "Why would I die?", "promised_payoff": "What you'd need to survive."},
            {"title_id": "TTL-004", "title": "Fire, Fat, and Fur: The Ice Age Survival Formula", "curiosity_score": 0.85, "clarity_score": 0.9, "specificity_score": 0.8, "novelty_score": 0.65, "truthfulness_score": 1.0, "thesis_alignment": 0.92, "payoff_alignment": 0.88, "mobile_readability": 0.9, "overall_score": 0.86, "risk_flags": [], "promised_question": "What's the formula?", "promised_payoff": "Three pillars explained."},
            {"title_id": "TTL-005", "title": "What Neanderthals Knew About Cold That You Don't", "curiosity_score": 0.95, "clarity_score": 0.8, "specificity_score": 0.75, "novelty_score": 0.8, "truthfulness_score": 0.9, "thesis_alignment": 0.75, "payoff_alignment": 0.7, "mobile_readability": 0.85, "overall_score": 0.83, "risk_flags": [], "promised_question": "What did they know?", "promised_payoff": "Ancient survival wisdom revealed."},
            {"title_id": "TTL-006", "title": "The Secret to Surviving Ice Age Winters (It Wasn't Just Fire)", "curiosity_score": 0.92, "clarity_score": 0.88, "specificity_score": 0.75, "novelty_score": 0.7, "truthfulness_score": 0.95, "thesis_alignment": 0.9, "payoff_alignment": 0.82, "mobile_readability": 0.88, "overall_score": 0.86, "risk_flags": [], "promised_question": "What else helped?", "promised_payoff": "More than just fire."},
            {"title_id": "TTL-007", "title": "How Our Ancestors Turned Deadly Winters Into a 200,000-Year Advantage", "curiosity_score": 0.88, "clarity_score": 0.75, "specificity_score": 0.8, "novelty_score": 0.7, "truthfulness_score": 0.92, "thesis_alignment": 0.88, "payoff_alignment": 0.85, "mobile_readability": 0.8, "overall_score": 0.83, "risk_flags": [], "promised_question": "How did they gain an advantage?", "promised_payoff": "Survival strategies explained."},
            {"title_id": "TTL-008", "title": "5 Things Ancient Humans Did to Survive Ice Age Winters", "curiosity_score": 0.85, "clarity_score": 0.92, "specificity_score": 0.78, "novelty_score": 0.6, "truthfulness_score": 1.0, "thesis_alignment": 0.8, "payoff_alignment": 0.78, "mobile_readability": 0.92, "overall_score": 0.82, "risk_flags": [], "promised_question": "What 5 things?", "promised_payoff": "Five strategies listed."},
            {"title_id": "TTL-009", "title": "Scientists Just Revealed How Neanderthals Survived Brutal Winters", "curiosity_score": 0.9, "clarity_score": 0.78, "specificity_score": 0.7, "novelty_score": 0.75, "truthfulness_score": 0.88, "thesis_alignment": 0.72, "payoff_alignment": 0.7, "mobile_readability": 0.82, "overall_score": 0.79, "risk_flags": ["title_overpromise"], "promised_question": "What did scientists reveal?", "promised_payoff": "Scientific findings."},
            {"title_id": "TTL-010", "title": "The Survival Kit That Kept Ice Age Humans Alive for Generations", "curiosity_score": 0.87, "clarity_score": 0.85, "specificity_score": 0.8, "novelty_score": 0.65, "truthfulness_score": 0.95, "thesis_alignment": 0.85, "payoff_alignment": 0.82, "mobile_readability": 0.88, "overall_score": 0.83, "risk_flags": [], "promised_question": "What's in the kit?", "promised_payoff": "Items that enabled survival."},
            {"title_id": "TTL-011", "title": "This Is What Actually Happened During Ice Age Winters", "curiosity_score": 0.83, "clarity_score": 0.9, "specificity_score": 0.75, "novelty_score": 0.6, "truthfulness_score": 0.92, "thesis_alignment": 0.8, "payoff_alignment": 0.78, "mobile_readability": 0.9, "overall_score": 0.81, "risk_flags": [], "promised_question": "What actually happened?", "promised_payoff": "True events revealed."},
            {"title_id": "TTL-012", "title": "The Bone Huts, Fire Pits, and Fat Reserves That Saved Humanity", "curiosity_score": 0.88, "clarity_score": 0.78, "specificity_score": 0.85, "novelty_score": 0.7, "truthfulness_score": 0.95, "thesis_alignment": 0.88, "payoff_alignment": 0.85, "mobile_readability": 0.8, "overall_score": 0.84, "risk_flags": [], "promised_question": "What saved humanity?", "promised_payoff": "Three specific elements."},
            {"title_id": "TTL-013", "title": "You Share DNA With People Who Survived Ice Age Winters", "curiosity_score": 0.82, "clarity_score": 0.88, "specificity_score": 0.7, "novelty_score": 0.68, "truthfulness_score": 0.9, "thesis_alignment": 0.75, "payoff_alignment": 0.72, "mobile_readability": 0.88, "overall_score": 0.79, "risk_flags": [], "promised_question": "How did my relatives survive?", "promised_payoff": "DNA connection explained."},
            {"title_id": "TTL-014", "title": "Mammoths, Fire, and Cooperation: The Ice Age Survival Story", "curiosity_score": 0.86, "clarity_score": 0.82, "specificity_score": 0.78, "novelty_score": 0.62, "truthfulness_score": 1.0, "thesis_alignment": 0.9, "payoff_alignment": 0.88, "mobile_readability": 0.85, "overall_score": 0.84, "risk_flags": [], "promised_question": "What was the story?", "promised_payoff": "Three key elements."},
            {"title_id": "TTL-015", "title": "The Answer to Surviving Ice Age Winters Is Simpler Than You Think", "curiosity_score": 0.9, "clarity_score": 0.85, "specificity_score": 0.65, "novelty_score": 0.72, "truthfulness_score": 0.88, "thesis_alignment": 0.78, "payoff_alignment": 0.75, "mobile_readability": 0.88, "overall_score": 0.82, "risk_flags": [], "promised_question": "What's the simple answer?", "promised_payoff": "A counterintuitive reveal."},
            {"title_id": "TTL-016", "title": "What Archaeology Tells Us About Surviving the Coldest Eras", "curiosity_score": 0.78, "clarity_score": 0.88, "specificity_score": 0.8, "novelty_score": 0.6, "truthfulness_score": 0.92, "thesis_alignment": 0.82, "payoff_alignment": 0.8, "mobile_readability": 0.85, "overall_score": 0.81, "risk_flags": [], "promised_question": "What does archaeology say?", "promised_payoff": "Archaeological findings."},
            {"title_id": "TTL-017", "title": "The Ice Age Survival Secret Hidden in Mammoth Bones", "curiosity_score": 0.93, "clarity_score": 0.78, "specificity_score": 0.75, "novelty_score": 0.78, "truthfulness_score": 0.9, "thesis_alignment": 0.85, "payoff_alignment": 0.8, "mobile_readability": 0.82, "overall_score": 0.83, "risk_flags": [], "promised_question": "What's the secret?", "promised_payoff": "Mammoth bone usage revealed."},
            {"title_id": "TTL-018", "title": "Together Was the Only Way: How Early Humans Beat the Cold", "curiosity_score": 0.85, "clarity_score": 0.88, "specificity_score": 0.75, "novelty_score": 0.7, "truthfulness_score": 0.92, "thesis_alignment": 0.95, "payoff_alignment": 0.9, "mobile_readability": 0.85, "overall_score": 0.85, "risk_flags": [], "promised_question": "How did cooperation help?", "promised_payoff": "The cooperation thesis."},
            {"title_id": "TTL-019", "title": "What Really Kept Early Humans Warm During Ice Age Winters", "curiosity_score": 0.91, "clarity_score": 0.85, "specificity_score": 0.72, "novelty_score": 0.68, "truthfulness_score": 0.92, "thesis_alignment": 0.82, "payoff_alignment": 0.78, "mobile_readability": 0.88, "overall_score": 0.82, "risk_flags": [], "promised_question": "What kept them warm?", "promised_payoff": "Real survival mechanisms."},
            {"title_id": "TTL-020", "title": "The Shocking Truth About How Humans Survived Ice Ages", "curiosity_score": 0.88, "clarity_score": 0.8, "specificity_score": 0.68, "novelty_score": 0.72, "truthfulness_score": 0.88, "thesis_alignment": 0.8, "payoff_alignment": 0.75, "mobile_readability": 0.85, "overall_score": 0.81, "risk_flags": [], "promised_question": "What's the shocking truth?", "promised_payoff": "A surprising revelation."},
            {"title_id": "TTL-021", "title": "Fire Was Just the Beginning: Ice Age Survival Strategies", "curiosity_score": 0.87, "clarity_score": 0.82, "specificity_score": 0.75, "novelty_score": 0.7, "truthfulness_score": 0.9, "thesis_alignment": 0.88, "payoff_alignment": 0.82, "mobile_readability": 0.85, "overall_score": 0.83, "risk_flags": [], "promised_question": "What else mattered?", "promised_payoff": "Beyond fire: more strategies."},
            {"title_id": "TTL-022", "title": "The Science of Staying Alive: Ice Age Human Adaptations", "curiosity_score": 0.8, "clarity_score": 0.9, "specificity_score": 0.82, "novelty_score": 0.6, "truthfulness_score": 0.95, "thesis_alignment": 0.78, "payoff_alignment": 0.75, "mobile_readability": 0.88, "overall_score": 0.81, "risk_flags": [], "promised_question": "What science helped?", "promised_payoff": "Scientific analysis."},
            {"title_id": "TTL-023", "title": "How Ancient Humans Beat the Freeze (And What It Means for Us)", "curiosity_score": 0.86, "clarity_score": 0.85, "specificity_score": 0.75, "novelty_score": 0.68, "truthfulness_score": 0.88, "thesis_alignment": 0.82, "payoff_alignment": 0.78, "mobile_readability": 0.88, "overall_score": 0.82, "risk_flags": [], "promised_question": "How did they beat the freeze?", "promised_payoff": "Strategies and modern relevance."},
            {"title_id": "TTL-024", "title": "The Hidden History of Ice Age Survival", "curiosity_score": 0.84, "clarity_score": 0.88, "specificity_score": 0.7, "novelty_score": 0.72, "truthfulness_score": 0.9, "thesis_alignment": 0.78, "payoff_alignment": 0.75, "mobile_readability": 0.88, "overall_score": 0.81, "risk_flags": [], "promised_question": "What's the hidden history?", "promised_payoff": "Unknown history revealed."},
            {"title_id": "TTL-025", "title": "What a Single Ice Age Winter Taught Us About Survival", "curiosity_score": 0.82, "clarity_score": 0.85, "specificity_score": 0.72, "novelty_score": 0.65, "truthfulness_score": 0.88, "thesis_alignment": 0.8, "payoff_alignment": 0.78, "mobile_readability": 0.88, "overall_score": 0.8, "risk_flags": [], "promised_question": "What did the winter teach us?", "promised_payoff": "Lessons from Ice Age winters."},
        ],
        "selected_id": "TTL-001",
        "validated_against_script": True,
        "validation_note": "Title directly mirrors topic and matches final script content.",
        "review_status": "draft",
        "review_notes": "",
    },
    "hook": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "jkl012",
        },
        "candidates": [
            {
                "hook_id": "HOK-001",
                "text": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?",
                "curiosity": 0.95,
                "tension": 0.9,
                "clarity": 0.9,
                "specificity": 0.88,
                "payoff_potential": 0.92,
                "overall_score": 0.91,
                "risk_flags": [],
            },
            {
                "hook_id": "HOK-002",
                "text": "Somewhere in the Arctic, 30,000 years ago, a small group of humans had to survive temperatures that would kill you in minutes. Here's how they did it.",
                "curiosity": 0.88,
                "tension": 0.95,
                "clarity": 0.85,
                "specificity": 0.82,
                "payoff_potential": 0.85,
                "overall_score": 0.87,
                "risk_flags": [],
            },
            {
                "hook_id": "HOK-003",
                "text": "Fire, fur, fat, and friendship. Four things. That's all it took to survive the deadliest winters in human history.",
                "curiosity": 0.85,
                "tension": 0.78,
                "clarity": 0.92,
                "specificity": 0.85,
                "payoff_potential": 0.88,
                "overall_score": 0.86,
                "risk_flags": [],
            },
            {
                "hook_id": "HOK-004",
                "text": "The last Ice Age lasted 100,000 years. Early humans didn't just endure it — they thrived. How?",
                "curiosity": 0.82,
                "tension": 0.8,
                "clarity": 0.88,
                "specificity": 0.75,
                "payoff_potential": 0.85,
                "overall_score": 0.82,
                "risk_flags": [],
            },
            {
                "hook_id": "HOK-005",
                "text": "You're warm right now. Your house has heating. Your clothes are designed for cold. And still, winter is hard. Imagine facing an Ice Age with nothing but stone tools.",
                "curiosity": 0.9,
                "tension": 0.88,
                "clarity": 0.8,
                "specificity": 0.78,
                "payoff_potential": 0.82,
                "overall_score": 0.84,
                "risk_flags": [],
            },
        ],
        "selected_id": "HOK-001",
        "review_status": "draft",
        "review_notes": "",
    },
    "blueprint": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T00:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "mno345",
        },
        "beats": [
            {
                "beat_id": "B-001", "purpose": "hook",
                "claim_ids": [],
                "emotional_state": "tense",
                "curiosity_level": 0.95, "information_density": 0.4,
                "visual_potential": 0.9, "estimated_duration_sec": 8.0,
            },
            {
                "beat_id": "B-002", "purpose": "setup",
                "claim_ids": ["CLM-002"],
                "emotional_state": "neutral",
                "curiosity_level": 0.75, "information_density": 0.7,
                "visual_potential": 0.85, "estimated_duration_sec": 10.0,
            },
            {
                "beat_id": "B-003", "purpose": "first_discovery",
                "claim_ids": ["CLM-003", "CLM-004"],
                "emotional_state": "calm",
                "curiosity_level": 0.8, "information_density": 0.75,
                "visual_potential": 0.88, "estimated_duration_sec": 10.0,
            },
            {
                "beat_id": "B-004", "purpose": "evidence",
                "claim_ids": ["CLM-003"],
                "emotional_state": "warm",
                "curiosity_level": 0.7, "information_density": 0.7,
                "visual_potential": 0.85, "estimated_duration_sec": 12.0,
            },
            {
                "beat_id": "B-005", "purpose": "escalation",
                "claim_ids": ["CLM-005", "CLM-006"],
                "emotional_state": "neutral",
                "curiosity_level": 0.72, "information_density": 0.8,
                "visual_potential": 0.8, "estimated_duration_sec": 10.0,
            },
            {
                "beat_id": "B-006", "purpose": "payoff",
                "claim_ids": ["CLM-001", "CLM-005"],
                "emotional_state": "triumphant",
                "curiosity_level": 0.65, "information_density": 0.5,
                "visual_potential": 0.75, "estimated_duration_sec": 12.0,
            },
        ],
        "total_estimated_duration_sec": 62.0,
        "progression_flags": ["tension_then_relief", "discovery_to_payoff"],
        "warnings": [],
    },
    "script": {
        "versions": [
            {
                "version_type": "draft",
                "artifact_version": {
                    "version": "v1", "created_at": "2024-01-01T00:00:00Z",
                    "provider": "openai", "model": "gpt-4o", "configuration": {},
                    "input_hash": "pqr678",
                },
                "segments": [
                    {"segment_id": "SEG-001", "order": 0, "narration": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?", "purpose": "hook", "beat_id": "B-001", "claim_ids": [], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "tense", "curiosity_level": 0.95, "information_density": 0.4, "estimated_duration_sec": 8.0, "visual_intent": "Lone figure shivers in snowy landscape", "transition_intent": ""},
                    {"segment_id": "SEG-002", "order": 1, "narration": "The first ingredient was fire. Hearths dug into cave floors, dated to four hundred thousand years ago, suggest they kept it burning almost constantly.", "purpose": "setup", "beat_id": "B-002", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.75, "information_density": 0.7, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: hearth with timeline", "transition_intent": "The warmth of fire leads to what else kept them warm"},
                    {"segment_id": "SEG-003", "order": 2, "narration": "Bone awls, found from at least seventy thousand years ago, were used to punch holes through hides and sew them together into tailored clothing.", "purpose": "first_discovery", "beat_id": "B-003", "claim_ids": ["CLM-003", "CLM-004"], "source_ids": ["SRC-00000002", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "calm", "curiosity_level": 0.8, "information_density": 0.75, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: bone awl and stitched hide", "transition_intent": "Clothing by itself isn't enough — you need shelter too"},
                    {"segment_id": "SEG-004", "order": 3, "narration": "Some groups built huts from mammoth bones, stacking ribs like logs and draping hides over them. Others shared caves. Either way, the principle is the same: a small space, heated by a body or a fire, stays warmer than open air.", "purpose": "evidence", "beat_id": "B-004", "claim_ids": ["CLM-003"], "source_ids": ["SRC-00000003"], "certainty_level": "supported", "emotional_state": "warm", "curiosity_level": 0.7, "information_density": 0.7, "estimated_duration_sec": 12.0, "visual_intent": "Mammoth-bone hut diagram and interior scene", "transition_intent": "Shelter needs energy — and food was the hardest part"},
                    {"segment_id": "SEG-005", "order": 4, "narration": "Food was the trickiest part. Plants freeze, so Ice Age humans leaned on fat — from mammoths, bison, reindeer. A single mammoth could feed a band of thirty for weeks, and its fat could be rendered into oil for lamps.", "purpose": "escalation", "beat_id": "B-005", "claim_ids": ["CLM-005", "CLM-006"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.72, "information_density": 0.8, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: mammoth and fat storage", "transition_intent": "But none of this worked alone"},
                    {"segment_id": "SEG-006", "order": 5, "narration": "None of this worked alone. Fire, clothing, shelter, and food all required cooperation — splitting hunting parties, sharing hides, keeping watch through the night. So the real answer to how ancient humans survived deadly winters isn't any single invention. It's that they learned to depend on each other.", "purpose": "payoff", "beat_id": "B-006", "claim_ids": ["CLM-001", "CLM-005"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "triumphant", "curiosity_level": 0.65, "information_density": 0.5, "estimated_duration_sec": 12.0, "visual_intent": "Group huddled around fire, warm faces lit", "transition_intent": ""},
                ],
                "total_word_count": 152,
                "total_duration_sec": 62.0,
                "is_final": False,
            },
            {
                "version_type": "revision",
                "artifact_version": {
                    "version": "v2", "created_at": "2024-01-01T01:00:00Z",
                    "provider": "openai", "model": "gpt-4o", "configuration": {},
                    "input_hash": "stu901",
                },
                "segments": [
                    {"segment_id": "SEG-001", "order": 0, "narration": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?", "purpose": "hook", "beat_id": "B-001", "claim_ids": [], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "tense", "curiosity_level": 0.95, "information_density": 0.4, "estimated_duration_sec": 8.0, "visual_intent": "Lone figure shivers in snowy landscape", "transition_intent": ""},
                    {"segment_id": "SEG-002", "order": 1, "narration": "The first ingredient was fire. Hearths dug into cave floors, dated to four hundred thousand years ago, suggest they kept it burning almost constantly. Fire wasn't just warmth — it cooked roots and dried hides.", "purpose": "setup", "beat_id": "B-002", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.78, "information_density": 0.72, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: hearth with timeline", "transition_intent": "Fire was essential but not sufficient"},
                    {"segment_id": "SEG-003", "order": 2, "narration": "Bone awls, found from at least seventy thousand years ago, were used to punch holes through hides and sew them together. Tailored clothing traps still air against the skin — the difference between sleep and hypothermia.", "purpose": "first_discovery", "beat_id": "B-003", "claim_ids": ["CLM-003", "CLM-004"], "source_ids": ["SRC-00000002", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "calm", "curiosity_level": 0.82, "information_density": 0.78, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: bone awl and stitched hide", "transition_intent": "Clothing by itself isn't enough — you need shelter too"},
                    {"segment_id": "SEG-004", "order": 3, "narration": "Some groups built huts from mammoth bones, stacking ribs like logs and draping hides over them. Others shared caves. Either way: a small space, heated by a body or a fire, stays warmer than open air.", "purpose": "evidence", "beat_id": "B-004", "claim_ids": ["CLM-003"], "source_ids": ["SRC-00000003"], "certainty_level": "supported", "emotional_state": "warm", "curiosity_level": 0.72, "information_density": 0.72, "estimated_duration_sec": 12.0, "visual_intent": "Mammoth-bone hut diagram and interior scene", "transition_intent": "Shelter needs energy — and food was the hardest part"},
                    {"segment_id": "SEG-005", "order": 4, "narration": "Food was the trickiest part. Plants freeze, so Ice Age humans leaned on fat — from mammoths, bison, reindeer. A single mammoth could feed a band of thirty for weeks, and its fat could be rendered into oil for lamps.", "purpose": "escalation", "beat_id": "B-005", "claim_ids": ["CLM-005", "CLM-006"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.74, "information_density": 0.82, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: mammoth and fat storage", "transition_intent": "But none of this worked alone"},
                    {"segment_id": "SEG-006", "order": 5, "narration": "None of this worked alone. Fire, clothing, shelter, and food all required cooperation — splitting hunting parties, sharing hides, keeping watch through the night. So the real answer to how ancient humans survived deadly winters isn't any single invention. It's that they learned to depend on each other.", "purpose": "payoff", "beat_id": "B-006", "claim_ids": ["CLM-001", "CLM-005"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "triumphant", "curiosity_level": 0.68, "information_density": 0.52, "estimated_duration_sec": 12.0, "visual_intent": "Group huddled around fire, warm faces lit", "transition_intent": ""},
                ],
                "total_word_count": 158,
                "total_duration_sec": 62.0,
                "is_final": False,
            },
            {
                "version_type": "final",
                "artifact_version": {
                    "version": "v3", "created_at": "2024-01-01T02:00:00Z",
                    "provider": "openai", "model": "gpt-4o", "configuration": {},
                    "input_hash": "vwx234",
                },
                "segments": [
                    {"segment_id": "SEG-001", "order": 0, "narration": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?", "purpose": "hook", "beat_id": "B-001", "claim_ids": [], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "tense", "curiosity_level": 0.95, "information_density": 0.4, "estimated_duration_sec": 8.0, "visual_intent": "Lone figure shivers in snowy landscape", "transition_intent": ""},
                    {"segment_id": "SEG-002", "order": 1, "narration": "The first ingredient was fire. Hearths dug into cave floors, dated to four hundred thousand years ago, suggest they kept it burning almost constantly. Fire wasn't just warmth — it cooked roots and dried hides.", "purpose": "setup", "beat_id": "B-002", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.78, "information_density": 0.72, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: hearth with timeline", "transition_intent": "Fire was essential but not sufficient"},
                    {"segment_id": "SEG-003", "order": 2, "narration": "Bone awls, found from at least seventy thousand years ago, were used to punch holes through hides and sew them together. Tailored clothing traps still air against the skin — the difference between sleep and hypothermia.", "purpose": "first_discovery", "beat_id": "B-003", "claim_ids": ["CLM-003", "CLM-004"], "source_ids": ["SRC-00000002", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "calm", "curiosity_level": 0.82, "information_density": 0.78, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: bone awl and stitched hide", "transition_intent": "Clothing by itself isn't enough — you need shelter too"},
                    {"segment_id": "SEG-004", "order": 3, "narration": "Some groups built huts from mammoth bones, stacking ribs like logs and draping hides over them. Others shared caves. Either way: a small space, heated by a body or a fire, stays warmer than open air.", "purpose": "evidence", "beat_id": "B-004", "claim_ids": ["CLM-003"], "source_ids": ["SRC-00000003"], "certainty_level": "supported", "emotional_state": "warm", "curiosity_level": 0.72, "information_density": 0.72, "estimated_duration_sec": 12.0, "visual_intent": "Mammoth-bone hut diagram and interior scene", "transition_intent": "Shelter needs energy — and food was the hardest part"},
                    {"segment_id": "SEG-005", "order": 4, "narration": "Food was the trickiest part. Plants freeze, so Ice Age humans leaned on fat — from mammoths, bison, reindeer. A single mammoth could feed a band of thirty for weeks, and its fat could be rendered into oil for lamps.", "purpose": "escalation", "beat_id": "B-005", "claim_ids": ["CLM-005", "CLM-006"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "neutral", "curiosity_level": 0.74, "information_density": 0.82, "estimated_duration_sec": 10.0, "visual_intent": "Diagram: mammoth and fat storage", "transition_intent": "But none of this worked alone"},
                    {"segment_id": "SEG-006", "order": 5, "narration": "None of this worked alone. Fire, clothing, shelter, and food all required cooperation — splitting hunting parties, sharing hides, keeping watch through the night. So the real answer to how ancient humans survived deadly winters isn't any single invention. It's that they learned to depend on each other.", "purpose": "payoff", "beat_id": "B-006", "claim_ids": ["CLM-001", "CLM-005"], "source_ids": ["SRC-00000001", "SRC-00000003"], "certainty_level": "supported", "emotional_state": "triumphant", "curiosity_level": 0.68, "information_density": 0.52, "estimated_duration_sec": 12.0, "visual_intent": "Group huddled around fire, warm faces lit", "transition_intent": ""},
                ],
                "total_word_count": 158,
                "total_duration_sec": 62.0,
                "is_final": True,
            },
        ],
        "draft_version": "draft",
        "critique_version": "",
        "revision_version": "revision",
        "final_version": "final",
        "active_version": "draft",
        "review_status": "draft",
        "review_notes": "",
    },
    "traceability": {
        "entries": [
            {"segment_id": "SEG-002", "claim_text_excerpt": "controlled use of fire dates back at least 400,000 years", "certainty_level": "supported", "claim_ids": ["CLM-002"], "source_ids": ["SRC-00000001"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            {"segment_id": "SEG-003", "claim_text_excerpt": "Tailored clothing, evidenced by bone awls, appeared at least 70,000 years ago", "certainty_level": "supported", "claim_ids": ["CLM-004"], "source_ids": ["SRC-00000002"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            {"segment_id": "SEG-004", "claim_text_excerpt": "Mammoth-bone huts have been excavated in Ukraine and Russia", "certainty_level": "supported", "claim_ids": ["CLM-003"], "source_ids": ["SRC-00000003"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            {"segment_id": "SEG-005", "claim_text_excerpt": "Ice Age humans hunted megafauna for both food and warm hides", "certainty_level": "supported", "claim_ids": ["CLM-005"], "source_ids": ["SRC-00000001", "SRC-00000003"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            {"segment_id": "SEG-005", "claim_text_excerpt": "Fat consumption from megafauna was critical for surviving extreme cold", "certainty_level": "inferential", "claim_ids": ["CLM-006"], "source_ids": ["SRC-00000001"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
            {"segment_id": "SEG-006", "claim_text_excerpt": "Neanderthals lived through glacial winters for over 200,000 years", "certainty_level": "supported", "claim_ids": ["CLM-001"], "source_ids": ["SRC-00000001", "SRC-00000002"], "is_supported": True, "distortion_flags": [], "distortion_detail": ""},
        ],
        "unsupported_entries": [],
        "critical_unsupported": [],
        "research_to_script_coverage": 0.6,
        "script_to_research_traceability": 0.83,
        "distortion_warnings": [],
        "unused_high_importance_claim_ids": ["CLM-007"],
    },
    "critique": {
        "artifact_version": {
            "version": "v1-crit", "created_at": "2024-01-01T00:30:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "yza567",
        },
        "findings": [
            {
                "finding_id": "CRT-001",
                "severity": "critical",
                "segment_id": "SEG-005",
                "category": "pacing",
                "problem": "The food segment contains the phrase 'A single mammoth could feed a band of thirty for weeks' — this specific claim about thirty people needs a source and may compress the timeline unnecessarily.",
                "evidence": "CLM-005 and CLM-006 don't quantify group sizes this precisely.",
                "recommendation": "Replace with 'could sustain a hunting band for extended periods' to avoid unverifiable specificity.",
            },
            {
                "finding_id": "CRT-002",
                "severity": "warning",
                "segment_id": "SEG-002",
                "category": "redundancy",
                "problem": "The phrase 'Fire wasn't just warmth' appears in both the script and is implied by the visual intent description, creating redundancy between audio and visual channels.",
                "evidence": "Script says 'Fire wasn't just warmth' and visual is a hearth diagram.",
                "recommendation": "Reconsider phrasing in voiceover to avoid repeating what the diagram makes obvious.",
            },
            {
                "finding_id": "CRT-003",
                "severity": "info",
                "segment_id": "SEG-003",
                "category": "clarity",
                "problem": "The phrase 'Tailored clothing traps still air against the skin' is technically accurate but may be opaque to general audiences without an analogy.",
                "evidence": "Air insulation concept is familiar to scientists but less so to laypeople.",
                "recommendation": "Consider adding a brief analogy like 'just like a puffy winter jacket.'",
            },
        ],
        "critical_count": 1,
        "warning_count": 1,
        "info_count": 1,
        "hardest_section": "SEG-005 (food/fat content)",
        "weakest_point": "Precise group-size claim in segment 5 lacks sourcing",
        "best_point": "SEG-006 (payoff) lands the thesis effectively with strong emotional arc",
        "would_viewer_leave_at": "SEG-004 — the mammoth bone hut diagram is visually compelling but the narration is dense",
        "pacing_flags": ["SEG-005 dense", "SEG-004 slow visual"],
        "repetition_flags": [],
        "ai_pattern_flags": [],
    },
    "retention": {
        "segment_retentions": [
            {"segment_id": "SEG-001", "curiosity": 0.95, "new_information": 0.9, "tension": 0.9, "visual_change": 0.85, "payoff_distance": 0.9, "emotional_change": 0.7, "dropoff_risk": 0.1, "retention_score": 0.85},
            {"segment_id": "SEG-002", "curiosity": 0.75, "new_information": 0.8, "tension": 0.4, "visual_change": 0.75, "payoff_distance": 0.75, "emotional_change": 0.2, "dropoff_risk": 0.2, "retention_score": 0.61},
            {"segment_id": "SEG-003", "curiosity": 0.8, "new_information": 0.85, "tension": 0.35, "visual_change": 0.8, "payoff_distance": 0.65, "emotional_change": 0.25, "dropoff_risk": 0.25, "retention_score": 0.65},
            {"segment_id": "SEG-004", "curiosity": 0.7, "new_information": 0.75, "tension": 0.3, "visual_change": 0.85, "payoff_distance": 0.55, "emotional_change": 0.3, "dropoff_risk": 0.3, "retention_score": 0.59},
            {"segment_id": "SEG-005", "curiosity": 0.72, "new_information": 0.8, "tension": 0.45, "visual_change": 0.7, "payoff_distance": 0.4, "emotional_change": 0.2, "dropoff_risk": 0.35, "retention_score": 0.61},
            {"segment_id": "SEG-006", "curiosity": 0.65, "new_information": 0.6, "tension": 0.5, "visual_change": 0.7, "payoff_distance": 0.1, "emotional_change": 0.8, "dropoff_risk": 0.05, "retention_score": 0.62},
        ],
        "opening_risk": "Strong hook with high tension and curiosity; low dropoff risk",
        "middle_risk": "Segments 3-4 have moderate dropoff risk due to lower tension scores",
        "ending_risk": "Payoff segment recovers strongly with emotional change and proximity to resolution",
        "repetition_risks": [],
        "slow_sections": ["SEG-004 (shelter) — lower curiosity and emotional change"],
        "premature_reveals": [],
        "weak_payoff_flag": False,
        "overall_retention_score": 0.65,
    },
    "revision_history": {
        "entries": [
            {
                "revision_number": 1,
                "based_on_version": "draft",
                "critique_version_id": "CRT-001",
                "instructions_summary": "Addressed redundancy in SEG-002, tightened phrasing in SEG-003 and SEG-005, improved transition from SEG-004 to SEG-005.",
                "changes_made": [
                    "Added 'Fire wasn't just warmth — it cooked roots and dried hides' to SEG-002",
                    "Replaced 'Bone awls were used to punch holes through hides and sew them together' with more fluid version in SEG-003",
                    "Changed 'could feed a band of thirty' to 'could sustain a hunting band' in SEG-005",
                ],
                "created_at": "2024-01-01T01:00:00Z",
            },
        ],
        "current_revision_number": 1,
    },
    "storyboard_intent": {
        "artifact_version": {
            "version": "v1", "created_at": "2024-01-01T03:00:00Z",
            "provider": "openai", "model": "gpt-4o", "configuration": {},
            "input_hash": "bcd890",
        },
        "items": [
            {"segment_id": "SEG-001", "purpose": "Establish tension and isolate the central question", "visual_goal": "Lone stick figure shivers in a vast icy plain under a dark sky", "visual_mode": "environment", "characters": ["narrator"], "environment": "ice_age_plains", "props": ["snow", "wind_lines"], "camera_intent": "Slow zoom in on figure", "motion_intent": "Camera pushes in as figure shivers", "text_intent": "No text", "source_ids": [], "continuity_notes": "Set the cold visually before any warmth appears"},
            {"segment_id": "SEG-002", "purpose": "Introduce fire as the first pillar of survival", "visual_goal": "Diagram: glowing hearth cross-section with timeline from 400,000 BP to present", "visual_mode": "diagram", "characters": [], "environment": "diagram_white", "props": ["fire_glow", "timeline_bar"], "camera_intent": "Static, label callouts appear sequentially", "motion_intent": "Timeline bars extend left to right", "text_intent": "400,000 years of fire", "source_ids": ["SRC-00000001"], "continuity_notes": "Warm orange palette contrasts with previous cold scene"},
            {"segment_id": "SEG-003", "purpose": "Reveal the second pillar: tailored clothing", "visual_goal": "Diagram: bone awl photo + stitched hide cross-section with air-trap annotation", "visual_mode": "diagram", "characters": [], "environment": "diagram_white", "props": ["bone_awl", "stitched_hide"], "camera_intent": "Close-up on awl then pull back to show full garment", "motion_intent": "Stitching lines animate in one by one", "text_intent": "Tailored hide clothing", "source_ids": ["SRC-00000002", "SRC-00000003"], "continuity_notes": "Continue warm palette; no return to cold blues"},
            {"segment_id": "SEG-004", "purpose": "Show the third pillar: shelter", "visual_goal": "Diagram: mammoth-bone hut plan view + animated cutaway into interior with figures", "visual_mode": "diagram", "characters": ["narrator", "companion"], "environment": "cave_interior", "props": ["mammoth_bones", "hide_roof"], "camera_intent": "Plan view cross-fades to interior perspective", "motion_intent": "Bones stack animation then roof drapes over", "text_intent": "Mammoth-bone shelter", "source_ids": ["SRC-00000003"], "continuity_notes": "Interior warmth should feel intentional after the cold open"},
            {"segment_id": "SEG-005", "purpose": "Present the fourth pillar: high-fat food", "visual_goal": "Diagram: mammoth silhouette with fat/oil callout + calorie density comparison chart", "visual_mode": "diagram", "characters": [], "environment": "diagram_white", "props": ["mammoth_outline", "fat_drop"], "camera_intent": "Static with data callouts animating in", "motion_intent": "Fat-drop icon pulses to emphasize calorie density", "text_intent": "9 calories/gram — fat wins", "source_ids": ["SRC-00000001", "SRC-00000003"], "continuity_notes": "Keeps energy high; no slow sections visually"},
            {"segment_id": "SEG-006", "purpose": "Deliver the payoff: cooperation was the real answer", "visual_goal": "Group of stick figures huddled around fire inside cave, faces warm-lit, slightly triumphantly posed", "visual_mode": "character", "characters": ["narrator", "companion"], "environment": "cave_interior", "props": ["fire"], "camera_intent": "Slow pull-back to show the full group, then final wide shot", "motion_intent": "Warm glow expands outward to full frame", "text_intent": "Thesis statement: they depended on each other", "source_ids": ["SRC-00000001", "SRC-00000003"], "continuity_notes": "Full emotional payoff; camera should feel the warmth"},
        ],
        "visual_mode_counts": {"diagram": 4, "character": 1, "environment": 1},
    },
    "quality_score": {
        "thesis_strength": {"score": 0.87, "notes": "THS-001 has strong explanatory power and covers all major survival pillars"},
        "evidence_alignment": {"score": 0.85, "notes": "All script claims traceable to research; CLM-006 is inferential but acceptable"},
        "angle_strength": {"score": 0.88, "notes": "ANG-001 (survival formula) is well-structured with high visual potential"},
        "title_strength": {"score": 0.87, "notes": "TTL-001 directly mirrors the topic and validated against final script"},
        "hook_strength": {"score": 0.91, "notes": "HOK-001 has the highest overall score with excellent tension and payoff potential"},
        "narrative_structure": {"score": 0.78, "notes": "Six-beat structure is sound but middle section could be tighter"},
        "curiosity": {"score": 0.8, "notes": "Consistently high curiosity scores across segments; SEG-006 lowest but appropriate for payoff"},
        "pacing": {"score": 0.72, "notes": "SEG-004 flagged as slow; critique identified density issue in SEG-005"},
        "clarity": {"score": 0.82, "notes": "Generally clear; audience comprehension risk in SEG-003 air-trap explanation"},
        "information_density": {"score": 0.7, "notes": "SEG-002 and SEG-005 are information-dense; SEG-006 appropriately light for payoff"},
        "visual_potential": {"score": 0.85, "notes": "4 of 6 segments are diagram-ready; character scenes are emotionally grounded"},
        "fact_traceability": {"score": 0.83, "notes": "6 of 7 key claims traced; CLM-001 and CLM-005 have the most coverage"},
        "natural_language": {"score": 0.8, "notes": "AI pattern flagged as low-risk; redundancy issue in SEG-002 identified in critique"},
        "payoff": {"score": 0.88, "notes": "SEG-006 delivers the thesis effectively with strong emotional arc"},
        "ai_writing_risk": {"score": 0.15, "notes": "Low risk; no significant AI writing patterns detected"},
        "overall_score": 0.8,
        "dimension_scores": {
            "thesis_strength": 0.87, "evidence_alignment": 0.85, "angle_strength": 0.88,
            "title_strength": 0.87, "hook_strength": 0.91, "narrative_structure": 0.78,
            "curiosity": 0.8, "pacing": 0.72, "clarity": 0.82, "information_density": 0.7,
            "visual_potential": 0.85, "fact_traceability": 0.83, "natural_language": 0.8,
            "payoff": 0.88, "ai_writing_risk": 0.15,
        },
        "warnings": ["SEG-004 has moderate dropoff risk", "SEG-002 has minor redundancy between audio and visual"],
        "failures": [],
        "recommendations": ["Consider shortening SEG-004 narration", "Add analogy to SEG-003 air-trap explanation for general audiences"],
    },
}


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

MOCK_RESEARCH = {
    "topic": "How Did Ancient Humans Survive Deadly Winters?",
    "facts": [
        {
            "claim": "Neanderthals lived through glacial winters in Europe for "
                     "over 200,000 years, suggesting they had robust cold adaptations.",
            "sources": [
                {"url": "https://en.wikipedia.org/wiki/Neanderthal",
                 "title": "Neanderthal - Wikipedia",
                 "snippet": "Neanderthals inhabited Eurasia from ..."
                 },
            ],
            "confidence": 0.85,
        },
        {
            "claim": "The controlled use of fire, evidenced by hearths dating back "
                     "400,000 years, was central to surviving cold nights.",
            "sources": [
                {"url": "https://en.wikipedia.org/wiki/Control_of_fire_by_early_humans",
                 "title": "Control of fire by early humans - Wikipedia",
                 "snippet": "Evidence for the controlled use of fire ..."
                 },
            ],
            "confidence": 0.90,
        },
        {
            "claim": "Animal hides and tailored clothing appear in the archaeological "
                     "record at least 70,000 years ago, based on bone awls.",
            "sources": [
                {"url": "https://en.wikipedia.org/wiki/Clothing_in_ancient_history",
                 "title": "Clothing in ancient history - Wikipedia",
                 "snippet": "The earliest evidence of clothing ..."
                 },
            ],
            "confidence": 0.75,
        },
        {
            "claim": "Ice Age humans hunted megafauna like mammoths, providing "
                     "high-fat food and warm hides for entire communities.",
            "sources": [
                {"url": "https://en.wikipedia.org/wiki/Megafauna",
                 "title": "Megafauna - Wikipedia",
                 "snippet": "During the Pleistocene ..."
                 },
            ],
            "confidence": 0.80,
        },
    ],
    "open_questions": [
        "How much of survival was technology vs. biology?",
        "Did language play a role in coordinating group warmth?",
    ],
}


MOCK_THESIS = {
    "topic": "How Did Ancient Humans Survive Deadly Winters?",
    "claim": (
        "Ancient humans survived deadly winters not through any single trick, "
        "but by combining controlled fire, tailored clothing, cooperative "
        "shelter, and high-fat megafauna hunting into a flexible survival "
        "system."
    ),
    "counter_arguments": [
        "Some researchers argue genetics (cold-adapted body shape) mattered more.",
        "Latitude and ocean currents made some regions much milder than others.",
    ],
    "supporting_facts": [
        "Controlled fire use dates back at least 400,000 years.",
        "Bone awls for clothing appear by 70,000 years ago.",
        "Mammoth-bone huts have been excavated in Ukraine and Russia.",
        "Fat consumption from megafauna was critical calorie density.",
    ],
    "hook": "A single human, alone, would die in an Ice Age winter. The answer is in the word 'together.'",
}


MOCK_TITLES = {
    "candidates": [
        {
            "title": "How Did Ancient Humans Survive Deadly Winters?",
            "rationale": "Direct question, mirrors the original topic.",
        },
        {
            "title": "The Ice Age Trick That Kept Humans Alive",
            "rationale": "Curiosity gap, concrete noun.",
        },
        {
            "title": "Why You Wouldn't Last One Night in an Ice Age Cave",
            "rationale": "Second-person hook, stakes-driven.",
        },
        {
            "title": "Fire, Fat, and Fur: The Ice Age Survival Formula",
            "rationale": "Lists three concrete pillars, scannable.",
        },
        {
            "title": "What Neanderthals Knew About Cold That You Don't",
            "rationale": "Anchors to a known figure, implies a gap.",
        },
    ],
    "chosen_index": 0,
}


MOCK_SCRIPT = {
    "topic": "How Did Ancient Humans Survive Deadly Winters?",
    "sections": [
        {
            "name": "hook",
            "beats": [
                {
                    "text": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?",
                    "emotional_intent": "tense",
                },
            ],
        },
        {
            "name": "fire",
            "beats": [
                {
                    "text": "The first ingredient was fire. Hearths dug into cave floors, dated to four hundred thousand years ago, suggest they kept it burning almost constantly.",
                    "emotional_intent": "warm",
                },
                {
                    "text": "Fire wasn't just warmth. It cooked roots that humans can't digest raw, and it dried wet hides before they rotted.",
                    "emotional_intent": "neutral",
                },
            ],
        },
        {
            "name": "clothing",
            "beats": [
                {
                    "text": "Next: clothing. Bone awls, found from at least seventy thousand years ago, were used to punch holes through hides and sew them together.",
                    "emotional_intent": "calm",
                },
                {
                    "text": "Tailored clothing, not just draped fur, traps a layer of still air against the skin. That single layer can mean the difference between sleep and hypothermia.",
                    "emotional_intent": "calm",
                },
            ],
        },
        {
            "name": "shelter",
            "beats": [
                {
                    "text": "Then, shelter. Some groups built huts from mammoth bones, stacking ribs like logs and draping hides over them.",
                    "emotional_intent": "warm",
                },
                {
                    "text": "Others shared caves. Either way, the principle is the same: a small space, heated by a body or a fire, stays warmer than open air.",
                    "emotional_intent": "warm",
                },
            ],
        },
        {
            "name": "food",
            "beats": [
                {
                    "text": "Food was the trickiest part. Plants freeze, so Ice Age humans leaned on fat — from mammoths, bison, reindeer.",
                    "emotional_intent": "neutral",
                },
                {
                    "text": "A single mammoth could feed a band of thirty for weeks, and its fat could be rendered into oil for lamps.",
                    "emotional_intent": "triumphant",
                },
            ],
        },
        {
            "name": "together",
            "beats": [
                {
                    "text": "None of this worked alone. Fire, clothing, shelter, and food all required cooperation — splitting hunting parties, sharing hides, keeping watch through the night.",
                    "emotional_intent": "warm",
                },
                {
                    "text": "So the real answer to how ancient humans survived deadly winters isn't any single invention. It's that they learned to depend on each other.",
                    "emotional_intent": "triumphant",
                },
            ],
        },
    ],
}


MOCK_STORYBOARD = {
    "beats": [
        {"summary": "A lone figure shivers in a dark snowy landscape; camera pushes in.", "environment_id": "ice_age_plains", "characters": ["narrator"], "visual_intent": "tension, isolation", "duration_sec": 8.0},
        {"summary": "Cut to title card with the central question.", "environment_id": "title_card", "characters": [], "visual_intent": "text-driven", "duration_sec": 5.0},
        {"summary": "Diagram of a hearth: timeline + flame icon.", "environment_id": "cave_interior", "characters": [], "visual_intent": "educational diagram", "duration_sec": 10.0},
        {"summary": "Two early humans huddle by a fire in a cave; warm light.", "environment_id": "cave_interior", "characters": ["narrator", "companion"], "visual_intent": "warmth, intimacy", "duration_sec": 10.0},
        {"summary": "Diagram: bone awl + hide with stitching lines.", "environment_id": "diagram_white", "characters": [], "visual_intent": "educational diagram", "duration_sec": 10.0},
        {"summary": "Human wearing sewn fur cloak stands in wind.", "environment_id": "ice_age_plains", "characters": ["narrator"], "visual_intent": "demonstration", "duration_sec": 10.0},
        {"summary": "Diagram of mammoth-bone hut from above.", "environment_id": "diagram_white", "characters": [], "visual_intent": "diagram", "duration_sec": 10.0},
        {"summary": "Mammoth-bone hut in snow with figures going inside.", "environment_id": "mammoth_camp", "characters": ["narrator", "companion"], "visual_intent": "warmth inside cold", "duration_sec": 12.0},
        {"summary": "Diagram: fat storage / mammoth + oil lamp.", "environment_id": "diagram_white", "characters": [], "visual_intent": "diagram", "duration_sec": 10.0},
        {"summary": "Group shares food around a fire, faces lit.", "environment_id": "cave_interior", "characters": ["narrator", "companion"], "visual_intent": "community", "duration_sec": 12.0},
        {"summary": "Closing title card with thesis statement.", "environment_id": "title_card", "characters": [], "visual_intent": "text-driven", "duration_sec": 10.0},
    ],
}


def _mock_scene_json(job_topic: str = MOCK_THESIS["topic"]) -> dict:
    """Generate a SceneDefinition JSON fixture that matches the schema.

    Uses carefully chosen numeric timings that line up with the narration
    duration (sums to ~120s). The validator in `scene_definition.py` is
    strict about contiguity, references, and word-timing bounds; this
    fixture is engineered to pass all of those checks.
    """
    return {
        "meta": {
            "title": "How Did Ancient Humans Survive Deadly Winters?",
            "description": "",
            "fps": 30,
            "width": 1920,
            "height": 1080,
            "target_duration_sec": 120.0,
        },
        "style": {
            "primary_color": "#FF6B35",
            "accent_color": "#FFD166",
            "background_color": "#1D1D2C",
            "text_color": "#FFFFFF",
            "font_family": "Inter",
        },
        "characters": [
            {
                "id": "narrator",
                "name": "Narrator",
                "color": "#FF6B35",
                "default_pose": "stand",
                "description": "Stick-figure narrator in warm cloak.",
            },
            {
                "id": "companion",
                "name": "Companion",
                "color": "#FFD166",
                "default_pose": "stand",
                "description": "Stick-figure companion.",
            },
        ],
        "environments": [
            {"id": "ice_age_plains", "name": "Ice Age Plains", "background_asset": "backgrounds/ice_age_plains.png", "mood": "tense"},
            {"id": "title_card", "name": "Title Card", "background_asset": "backgrounds/title_card.png", "mood": "calm"},
            {"id": "cave_interior", "name": "Cave Interior", "background_asset": "backgrounds/cave_interior.png", "mood": "warm"},
            {"id": "diagram_white", "name": "Diagram White", "background_asset": "backgrounds/diagram_white.png", "mood": "calm"},
            {"id": "mammoth_camp", "name": "Mammoth Camp", "background_asset": "backgrounds/mammoth_camp.png", "mood": "warm"},
        ],
        "scenes": [
            # 0-8: hook narration
            {"id": "hook_narration", "kind": "narration", "start_sec": 0.0, "end_sec": 8.0,
             "environment_id": "ice_age_plains",
             "narration_text": "A single human, alone, would die in an Ice Age winter within hours. So how did our ancestors survive for hundreds of thousands of years?",
             "narration_words": [
                 {"word": "A", "start_sec": 0.1, "end_sec": 0.3},
                 {"word": "single", "start_sec": 0.3, "end_sec": 0.7},
                 {"word": "human,", "start_sec": 0.7, "end_sec": 1.3},
                 {"word": "alone,", "start_sec": 1.3, "end_sec": 1.8},
                 {"word": "would", "start_sec": 1.8, "end_sec": 2.2},
                 {"word": "die", "start_sec": 2.2, "end_sec": 2.6},
                 {"word": "in", "start_sec": 2.6, "end_sec": 2.8},
                 {"word": "an", "start_sec": 2.8, "end_sec": 3.0},
                 {"word": "Ice", "start_sec": 3.0, "end_sec": 3.4},
                 {"word": "Age", "start_sec": 3.4, "end_sec": 3.8},
                 {"word": "winter", "start_sec": 3.8, "end_sec": 4.4},
                 {"word": "within", "start_sec": 4.4, "end_sec": 4.9},
                 {"word": "hours.", "start_sec": 4.9, "end_sec": 5.5},
                 {"word": "So", "start_sec": 5.6, "end_sec": 5.9},
                 {"word": "how", "start_sec": 5.9, "end_sec": 6.2},
                 {"word": "did", "start_sec": 6.2, "end_sec": 6.5},
                 {"word": "our", "start_sec": 6.5, "end_sec": 6.8},
                 {"word": "ancestors", "start_sec": 6.8, "end_sec": 7.5},
                 {"word": "survive", "start_sec": 7.5, "end_sec": 7.9},
             ],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.2, "easing": "ease_in_out"},
             "actors": [{"character_id": "narrator", "x": 0.5, "y": 0.7, "scale": 1.0, "rotation_deg": 0, "pose": "hide", "enter_anim": "fade_in", "exit_anim": "none"}],
             "props": [{"kind": "snowflake", "x": 0.2, "y": 0.2, "scale": 0.6, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [], "sfx": [], "music": None,
             },
            # 8-13: title card
            {"id": "title_intro", "kind": "title", "start_sec": 8.0, "end_sec": 13.0,
             "environment_id": "title_card",
             "narration_text": "", "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [],
             "overlay_text": [
                 {"text": "How Did Ancient Humans Survive Deadly Winters?", "x": 0.5, "y": 0.5, "font_size": 64, "enter_at_sec": 8.2, "exit_at_sec": 12.8, "color": "#FFFFFF"}
             ],
             "sfx": [], "music": None,
             },
            # 13-23: fire diagram
            {"id": "fire_diagram", "kind": "diagram", "start_sec": 13.0, "end_sec": 23.0,
             "environment_id": "diagram_white",
             "narration_text": "The first ingredient was fire. Hearths dug into cave floors, dated to four hundred thousand years ago, suggest they kept it burning almost constantly. Fire wasn't just warmth. It cooked roots that humans can't digest raw, and it dried wet hides before they rotted.",
             "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [{"kind": "timeline", "x": 0.5, "y": 0.3, "scale": 1.0, "rotation_deg": 0, "enter_anim": "fade_in"}, {"kind": "fire", "x": 0.5, "y": 0.7, "scale": 0.8, "rotation_deg": 0, "enter_anim": "pop"}],
             "overlay_text": [
                 {"text": "Fire — 400,000 years of hearths", "x": 0.5, "y": 0.15, "font_size": 36, "enter_at_sec": 13.5, "exit_at_sec": 22.5, "color": "#1D1D2C"}
             ],
             "sfx": [], "music": None,
             },
            # 23-33: cave narrative
            {"id": "cave_narrative", "kind": "narration", "start_sec": 23.0, "end_sec": 33.0,
             "environment_id": "cave_interior",
             "narration_text": "Two early humans huddle by a fire in a cave; warm light.",
             "narration_words": [
                 {"word": "Two", "start_sec": 23.2, "end_sec": 23.6},
                 {"word": "early", "start_sec": 23.6, "end_sec": 24.0},
                 {"word": "humans", "start_sec": 24.0, "end_sec": 24.6},
                 {"word": "huddle", "start_sec": 24.6, "end_sec": 25.2},
                 {"word": "by", "start_sec": 25.2, "end_sec": 25.4},
                 {"word": "a", "start_sec": 25.4, "end_sec": 25.5},
                 {"word": "fire", "start_sec": 25.5, "end_sec": 25.9},
                 {"word": "in", "start_sec": 25.9, "end_sec": 26.1},
                 {"word": "a", "start_sec": 26.1, "end_sec": 26.2},
                 {"word": "cave.", "start_sec": 26.2, "end_sec": 26.8},
             ],
             "camera": {"pan_x": 0.5, "pan_y": 0.55, "zoom": 1.1, "easing": "ease_in_out"},
             "actors": [
                 {"character_id": "narrator", "x": 0.4, "y": 0.7, "scale": 1.0, "rotation_deg": 0, "pose": "sit", "enter_anim": "fade_in", "exit_anim": "none"},
                 {"character_id": "companion", "x": 0.6, "y": 0.7, "scale": 1.0, "rotation_deg": 0, "pose": "sit", "enter_anim": "fade_in", "exit_anim": "none"},
             ],
             "props": [{"kind": "fire", "x": 0.5, "y": 0.75, "scale": 0.6, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [], "sfx": [], "music": None,
             },
            # 33-43: clothing diagram
            {"id": "clothing_diagram", "kind": "diagram", "start_sec": 33.0, "end_sec": 43.0,
             "environment_id": "diagram_white",
             "narration_text": "Next: clothing. Bone awls, found from at least seventy thousand years ago, were used to punch holes through hides and sew them together. Tailored clothing, not just draped fur, traps a layer of still air against the skin.",
             "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [{"kind": "human_silhouette", "x": 0.5, "y": 0.55, "scale": 0.9, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [
                 {"text": "Bone awls → tailored hide clothing", "x": 0.5, "y": 0.15, "font_size": 32, "enter_at_sec": 33.5, "exit_at_sec": 42.5, "color": "#1D1D2C"}
             ],
             "sfx": [], "music": None,
             },
            # 43-53: narrator demo in plains
            {"id": "clothing_demo", "kind": "narration", "start_sec": 43.0, "end_sec": 53.0,
             "environment_id": "ice_age_plains",
             "narration_text": "That single layer can mean the difference between sleep and hypothermia.",
             "narration_words": [
                 {"word": "That", "start_sec": 43.2, "end_sec": 43.5},
                 {"word": "single", "start_sec": 43.5, "end_sec": 43.9},
                 {"word": "layer", "start_sec": 43.9, "end_sec": 44.4},
                 {"word": "can", "start_sec": 44.4, "end_sec": 44.7},
                 {"word": "mean", "start_sec": 44.7, "end_sec": 45.1},
                 {"word": "the", "start_sec": 45.1, "end_sec": 45.3},
                 {"word": "difference", "start_sec": 45.3, "end_sec": 46.0},
                 {"word": "between", "start_sec": 46.0, "end_sec": 46.5},
                 {"word": "sleep", "start_sec": 46.5, "end_sec": 47.0},
                 {"word": "and", "start_sec": 47.0, "end_sec": 47.2},
                 {"word": "hypothermia.", "start_sec": 47.2, "end_sec": 48.0},
             ],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.15, "easing": "ease_in_out"},
             "actors": [{"character_id": "narrator", "x": 0.5, "y": 0.65, "scale": 1.0, "rotation_deg": 0, "pose": "stand", "enter_anim": "slide_left", "exit_anim": "none"}],
             "props": [], "overlay_text": [], "sfx": [], "music": None,
             },
            # 53-63: shelter diagram
            {"id": "shelter_diagram", "kind": "diagram", "start_sec": 53.0, "end_sec": 63.0,
             "environment_id": "diagram_white",
             "narration_text": "Then, shelter. Some groups built huts from mammoth bones, stacking ribs like logs and draping hides over them.",
             "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [{"kind": "mountain", "x": 0.5, "y": 0.55, "scale": 1.0, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [
                 {"text": "Mammoth-bone huts", "x": 0.5, "y": 0.15, "font_size": 36, "enter_at_sec": 53.5, "exit_at_sec": 62.5, "color": "#1D1D2C"}
             ],
             "sfx": [], "music": None,
             },
            # 63-75: mammoth camp
            {"id": "camp_narrative", "kind": "narration", "start_sec": 63.0, "end_sec": 75.0,
             "environment_id": "mammoth_camp",
             "narration_text": "Others shared caves. Either way, the principle is the same: a small space, heated by a body or a fire, stays warmer than open air.",
             "narration_words": [
                 {"word": "Others", "start_sec": 63.3, "end_sec": 63.9},
                 {"word": "shared", "start_sec": 63.9, "end_sec": 64.4},
                 {"word": "caves.", "start_sec": 64.4, "end_sec": 65.0},
                 {"word": "Either", "start_sec": 65.2, "end_sec": 65.7},
                 {"word": "way,", "start_sec": 65.7, "end_sec": 66.1},
                 {"word": "the", "start_sec": 66.1, "end_sec": 66.3},
                 {"word": "principle", "start_sec": 66.3, "end_sec": 67.0},
                 {"word": "is", "start_sec": 67.0, "end_sec": 67.2},
                 {"word": "the", "start_sec": 67.2, "end_sec": 67.4},
                 {"word": "same:", "start_sec": 67.4, "end_sec": 67.9},
             ],
             "camera": {"pan_x": 0.55, "pan_y": 0.55, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [
                 {"character_id": "narrator", "x": 0.4, "y": 0.75, "scale": 0.9, "rotation_deg": 0, "pose": "walk", "enter_anim": "slide_left", "exit_anim": "none"},
                 {"character_id": "companion", "x": 0.6, "y": 0.75, "scale": 0.9, "rotation_deg": 0, "pose": "walk", "enter_anim": "slide_right", "exit_anim": "none"},
             ],
             "props": [{"kind": "cave", "x": 0.5, "y": 0.65, "scale": 1.0, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [], "sfx": [], "music": None,
             },
            # 75-85: food diagram
            {"id": "food_diagram", "kind": "diagram", "start_sec": 75.0, "end_sec": 85.0,
             "environment_id": "diagram_white",
             "narration_text": "Food was the trickiest part. Plants freeze, so Ice Age humans leaned on fat — from mammoths, bison, reindeer.",
             "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [{"kind": "animal_mammoth", "x": 0.5, "y": 0.6, "scale": 1.0, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [
                 {"text": "Fat: 9 calories per gram", "x": 0.5, "y": 0.15, "font_size": 36, "enter_at_sec": 75.5, "exit_at_sec": 84.5, "color": "#1D1D2C"}
             ],
             "sfx": [], "music": None,
             },
            # 85-97: community
            {"id": "community_narrative", "kind": "narration", "start_sec": 85.0, "end_sec": 97.0,
             "environment_id": "cave_interior",
             "narration_text": "None of this worked alone. Fire, clothing, shelter, and food all required cooperation.",
             "narration_words": [
                 {"word": "None", "start_sec": 85.3, "end_sec": 85.7},
                 {"word": "of", "start_sec": 85.7, "end_sec": 85.9},
                 {"word": "this", "start_sec": 85.9, "end_sec": 86.2},
                 {"word": "worked", "start_sec": 86.2, "end_sec": 86.8},
                 {"word": "alone.", "start_sec": 86.8, "end_sec": 87.4},
             ],
             "camera": {"pan_x": 0.5, "pan_y": 0.55, "zoom": 1.05, "easing": "ease_in_out"},
             "actors": [
                 {"character_id": "narrator", "x": 0.4, "y": 0.7, "scale": 1.0, "rotation_deg": 0, "pose": "celebrate", "enter_anim": "pop", "exit_anim": "none"},
                 {"character_id": "companion", "x": 0.6, "y": 0.7, "scale": 1.0, "rotation_deg": 0, "pose": "celebrate", "enter_anim": "pop", "exit_anim": "none"},
             ],
             "props": [{"kind": "fire", "x": 0.5, "y": 0.78, "scale": 0.6, "rotation_deg": 0, "enter_anim": "fade_in"}],
             "overlay_text": [], "sfx": [], "music": None,
             },
            # 97-107: conclusion diagram
            {"id": "conclusion_diagram", "kind": "diagram", "start_sec": 97.0, "end_sec": 107.0,
             "environment_id": "diagram_white",
             "narration_text": "So the real answer is that they learned to depend on each other.",
             "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [],
             "overlay_text": [
                 {"text": "Fire + Fur + Fat + Together = Survival", "x": 0.5, "y": 0.5, "font_size": 48, "enter_at_sec": 97.5, "exit_at_sec": 106.5, "color": "#FF6B35"}
             ],
             "sfx": [], "music": None,
             },
            # 107-120: closing title
            {"id": "closing_title", "kind": "title", "start_sec": 107.0, "end_sec": 120.0,
             "environment_id": "title_card",
             "narration_text": "", "narration_words": [],
             "camera": {"pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "ease_in_out"},
             "actors": [], "props": [],
             "overlay_text": [
                 {"text": "Thanks for watching", "x": 0.5, "y": 0.45, "font_size": 64, "enter_at_sec": 107.5, "exit_at_sec": 119.5, "color": "#FFFFFF"},
                 {"text": "Subscribe for more", "x": 0.5, "y": 0.6, "font_size": 36, "enter_at_sec": 108.0, "exit_at_sec": 119.5, "color": "#FFD166"}
             ],
             "sfx": [], "music": None,
             },
        ],
    }


# --------------------------------------------------------------------------
# Dispatcher: peek at the last user message to decide which fixture to return.
# --------------------------------------------------------------------------

_FIXTURES_BY_INTENT: list[tuple[re.Pattern[str], dict]] = [
    # Story Intelligence Engine fixtures (must match BEFORE the legacy thesis/research patterns below)
    (re.compile(r"story_package|story intelligence|thesis_candidates|angle_candidates|title_candidates|narrative_blueprint|script_segments|script_revision|claim_traceability|script_critique|retention_analysis|story_quality|thesis strategist|narrative blueprint|script segments|script critique|retention analysis|story quality|storyboard intent|angle strategist|hook strategist|scriptwriter|hostile.*reviewer|storyboard designer|storyboard_intent_generation|angle.*strategist|hook.*strategist", re.I), MOCK_STORY_PACKAGE),
    # Rich research package for Research Engine steps
    (re.compile(r"specific research questions|extract.*claims|analyze.*visual|analyze.*story|synthesize|contradiction|quality score|source quality|deduplicate|score.*sources|fetch.*sources|research questions", re.I), MOCK_RESEARCH_PACKAGE),
    # Legacy research for backward compatibility (must come BEFORE the generic "research" pattern)
    (re.compile(r"gather facts|gather research", re.I), MOCK_RESEARCH),
    # Generic research pattern (matches "research" but excludes above)
    (re.compile(r"research", re.I), MOCK_RESEARCH_PACKAGE),
    (re.compile(r"thesis|claim|counter", re.I), MOCK_THESIS),
    (re.compile(r"title candidates|list of titles", re.I), MOCK_TITLES),
    (re.compile(r"scene definition|scene JSON|emitted scenes|SceneDefinition|scene_definition|Scene_Definition|SCENE_DEFINITION_TASK", re.I), _mock_scene_json()),
    (re.compile(r"storyboard|scene breakdown", re.I), MOCK_STORYBOARD),
    # Default to script (most common LLM call from the pipeline).
    (re.compile(r".*", re.I), MOCK_SCRIPT),
]


class MockLLMProvider(LLMProvider):
    """Returns canned fixtures. Used when no API key is configured or in tests."""

    name = "mock"

    def complete(self, request: LLMRequest) -> LLMResponse:
        # Use the last user message as a routing hint.
        last_user = next(
            (m.content for m in reversed(request.messages) if m.role == "user"),
            "",
        )
        for pattern, fixture in _FIXTURES_BY_INTENT:
            if pattern.search(last_user):
                content = json.dumps(fixture)
                parsed = fixture if request.json_mode else None
                return LLMResponse(
                    content=content,
                    parsed_json=parsed,
                    usage={"model": "mock", "elapsed_sec": 0.0},
                )
        # Fallback (should be unreachable given the regex above).
        content = json.dumps(MOCK_SCRIPT)
        return LLMResponse(content=content, parsed_json=MOCK_SCRIPT if request.json_mode else None)
