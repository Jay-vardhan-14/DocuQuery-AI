"""Seed script — populate the database with demo users and documents.

Creates 3 users (admin, manager, employee) and 4 documents at each access
level, then processes them through the chunking + embedding pipeline.

Usage:
    # With real OpenAI embeddings (requires OPENAI_API_KEY):
    python -m scripts.seed

    # With random mock embeddings (no API key needed):
    python -m scripts.seed --mock-embeddings
"""

import argparse
import asyncio
import logging
import random
import sys
import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure app modules are importable
sys.path.insert(0, ".")

from app.config import settings
from app.database import async_session_factory, engine, init_db
from app.models.user import User
from app.models.document import Document
from app.models.chunk import DocumentChunk
from app.services.auth_service import hash_password
from app.services.chunking_service import chunk_document

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed Users
# ---------------------------------------------------------------------------

SEED_USERS = [
    {
        "email": "admin@docuquery.ai",
        "password": "password123",
        "full_name": "Admin User",
        "role": "admin",
    },
    {
        "email": "manager@docuquery.ai",
        "password": "password123",
        "full_name": "Manager User",
        "role": "manager",
    },
    {
        "email": "employee@docuquery.ai",
        "password": "password123",
        "full_name": "Employee User",
        "role": "employee",
    },
]

# ---------------------------------------------------------------------------
# Seed Documents — realistic placeholder content
# ---------------------------------------------------------------------------

SEED_DOCUMENTS = [
    {
        "title": "Company Overview 2024",
        "filename": "company_overview_2024.pdf",
        "access_level": "public",
        "content": """Company Overview 2024 — DocuQuery Technologies Inc.

Founded in 2020, DocuQuery Technologies is a leading provider of AI-powered document management and retrieval solutions. Headquartered in San Francisco, California, the company serves over 500 enterprise clients globally across financial services, healthcare, and technology sectors.

Mission Statement
Our mission is to make organizational knowledge instantly accessible through natural language, enabling every team member to make data-driven decisions faster. We believe that information locked inside documents is an untapped asset, and our platform unlocks that value securely and intelligently.

Core Products
DocuQuery AI Platform — Our flagship product provides retrieval-augmented generation (RAG) capabilities that allow users to ask questions in plain English and receive accurate, citation-backed answers drawn from their document corpus. The platform supports PDF, DOCX, and plain text files with enterprise-grade security.

DocuQuery Analytics — A companion analytics suite that provides insights into document usage patterns, query trends, and knowledge gaps within organizations. It helps leadership teams understand what information employees are searching for and whether existing documentation meets their needs.

Financial Highlights
For fiscal year 2024, DocuQuery Technologies reported revenue of $42 million, representing a 65% year-over-year increase. Annual recurring revenue (ARR) reached $38 million. The company achieved positive cash flow for the first time in Q3 2024 and projects profitability for the full fiscal year 2025.

The company raised a $25 million Series B round in March 2024, led by Gradient Ventures, with participation from existing investors Foundation Capital and Innovation Endeavors. Total funding to date stands at $40 million.

Team and Culture
DocuQuery employs 120 team members across engineering, product, sales, and operations. The engineering team comprises 65 engineers, with deep expertise in machine learning, natural language processing, and distributed systems. The company maintains a hybrid work policy, with offices in San Francisco and New York.

Our culture values intellectual curiosity, ownership mentality, and transparent communication. We run quarterly hackathons where team members can explore new ideas, and several current product features originated from hackathon projects.

Strategic Partnerships
We maintain technology partnerships with OpenAI, Google Cloud, Amazon Web Services, and Microsoft Azure. Our platform is available on the AWS Marketplace and Azure Marketplace, enabling streamlined procurement for enterprise customers.

Looking Ahead
In 2025, DocuQuery plans to launch multi-modal document understanding (supporting images and charts within documents), expand into the European market with a London office, and release an on-premises deployment option for regulated industries.""",
    },
    {
        "title": "Employee Onboarding Guide",
        "filename": "employee_onboarding_guide.docx",
        "access_level": "internal",
        "content": """Employee Onboarding Guide — DocuQuery Technologies

Welcome to DocuQuery Technologies! This guide will help you navigate your first 90 days and set you up for success. Please read through each section carefully and reach out to your manager or HR if you have any questions.

Week 1: Getting Started

Day 1 — Orientation and Setup
Your first day will begin with an orientation session at 9:00 AM. You will receive your company laptop, access credentials, and employee badge. IT will assist you in setting up your development environment, email, Slack, and other essential tools.

Required accounts to set up:
- Google Workspace (email, calendar, drive)
- Slack (company communication)
- GitHub (code repositories)
- Jira (project management)
- Confluence (documentation)
- 1Password (password management)

Day 2-3 — Team Introduction and Codebase Overview
Your manager will introduce you to your team and schedule 1-on-1 meetings with key collaborators. You will receive a walkthrough of the codebase architecture, deployment pipeline, and development workflow.

Day 4-5 — First Task
By the end of week 1, you should have completed your first pull request. This is typically a small bug fix or documentation improvement designed to familiarize you with our development workflow.

Week 2-4: Ramp-Up Period

During weeks 2 through 4, you will work on increasingly complex tasks with guidance from your onboarding buddy. Each new team member is paired with an experienced engineer who serves as a mentor during the first 90 days.

Key milestones:
- Complete the engineering onboarding checklist
- Attend at least two team standup meetings
- Submit three pull requests with passing CI/CD checks
- Complete all mandatory compliance training modules
- Read and understand the security policies document

Development Workflow
All code changes follow this workflow:
1. Create a feature branch from main
2. Implement changes with comprehensive tests
3. Open a pull request with a clear description
4. Obtain at least two code review approvals
5. Merge after CI/CD passes and approvals are received

We use continuous deployment — merged code is automatically deployed to staging, and after validation, promoted to production.

Benefits and Perks
- Health insurance (medical, dental, vision) — 100% coverage for employees, 75% for dependents
- 401(k) with 4% company match
- Unlimited PTO policy (minimum 15 days encouraged)
- $2,000 annual learning and development budget
- Monthly wellness stipend of $100
- Home office setup allowance of $1,500 for remote employees
- Quarterly team offsites and social events
- Commuter benefits for office-based employees

Performance Reviews
Performance reviews are conducted quarterly, with a lightweight check-in at the end of each quarter and a comprehensive review annually. Reviews are based on a framework that evaluates impact, technical excellence, collaboration, and leadership.

Promotion decisions are made semi-annually in January and July, with input from your manager, skip-level manager, and peer feedback.

IT Support
For technical issues, contact the IT helpdesk via Slack (#it-support) or email it-support@docuquery.ai. Response times are typically under 2 hours during business hours. For urgent issues (production outages, security incidents), use the PagerDuty escalation path documented in Confluence.""",
    },
    {
        "title": "Engineering Promotion Criteria",
        "filename": "engineering_promotion_criteria.pdf",
        "access_level": "confidential",
        "content": """Engineering Promotion Criteria — DocuQuery Technologies
CONFIDENTIAL — Manager Access Only

This document outlines the criteria and process for engineering promotions at DocuQuery Technologies. This information should be shared only with managers and above, and should not be distributed to individual contributors directly.

Engineering Levels

Level 1 — Junior Engineer (IC1)
Compensation range: $95,000 - $120,000 base + equity
Expectations: Completes well-defined tasks with guidance. Writes clean, tested code. Actively learns from code reviews. Communicates progress and blockers effectively.

Level 2 — Engineer (IC2)
Compensation range: $120,000 - $155,000 base + equity
Expectations: Independently owns features end-to-end. Mentors junior engineers. Contributes to architectural decisions. Identifies and resolves technical debt. Demonstrates strong debugging and problem-solving skills.

Level 3 — Senior Engineer (IC3)
Compensation range: $155,000 - $195,000 base + equity
Expectations: Drives major technical initiatives. Influences team-level architecture. Develops reusable frameworks and tools. Provides substantial code review feedback. Recognized as a domain expert in at least one area.

Level 4 — Staff Engineer (IC4)
Compensation range: $195,000 - $250,000 base + equity
Expectations: Sets technical direction across multiple teams. Solves ambiguous, high-impact problems. Mentors senior engineers. Drives engineering culture and best practices. Published thought leadership (blog posts, conference talks).

Level 5 — Principal Engineer (IC5)
Compensation range: $250,000 - $320,000 base + equity
Expectations: Company-wide technical leadership. Defines multi-year technical strategy. Represents the company externally. Makes critical build-vs-buy decisions. Direct impact on company revenue and product direction.

Promotion Process

1. Manager Nomination — Managers submit promotion packets quarterly, containing evidence of the candidate operating at the next level for at least 6 months.

2. Calibration Committee — A cross-functional committee of senior leaders reviews all nominations to ensure consistency across teams and prevent bias.

3. Skip-Level Endorsement — The candidate's skip-level manager must endorse the promotion, confirming that the candidate's impact warrants advancement.

4. Peer Feedback — The committee reviews structured feedback from 3-4 peers who have worked closely with the candidate.

5. Decision and Communication — Decisions are communicated by the end of the review cycle (January for H2 promotions, July for H1 promotions).

Equity Refresh Grants
In addition to base salary increases, promoted employees receive equity refresh grants. The target equity value by level:
- IC1 → IC2: $30,000 over 4 years
- IC2 → IC3: $60,000 over 4 years
- IC3 → IC4: $120,000 over 4 years
- IC4 → IC5: $200,000 over 4 years""",
    },
    {
        "title": "Executive Compensation Policy",
        "filename": "executive_compensation_policy.pdf",
        "access_level": "restricted",
        "content": """Executive Compensation Policy — DocuQuery Technologies
RESTRICTED — Admin Access Only

This document contains sensitive compensation information for executive leadership positions. Distribution is strictly limited to the CEO, CFO, VP of People, and board-level reviewers.

Executive Salary Bands (2024-2025)

Chief Executive Officer (CEO)
Base salary: $350,000 - $450,000
Annual bonus target: 50% of base
Equity: 2.5% - 4.0% of fully diluted shares, vesting over 4 years
Total compensation target: $1,200,000 - $2,500,000

Chief Technology Officer (CTO)
Base salary: $300,000 - $400,000
Annual bonus target: 40% of base
Equity: 1.5% - 2.5% of fully diluted shares
Total compensation target: $900,000 - $1,800,000

Chief Financial Officer (CFO)
Base salary: $280,000 - $360,000
Annual bonus target: 40% of base
Equity: 1.0% - 2.0% of fully diluted shares
Total compensation target: $750,000 - $1,500,000

Vice President of Engineering
Base salary: $260,000 - $340,000
Annual bonus target: 35% of base
Equity: 0.75% - 1.5% of fully diluted shares
Total compensation target: $650,000 - $1,200,000

Vice President of Product
Base salary: $250,000 - $330,000
Annual bonus target: 35% of base
Equity: 0.75% - 1.5% of fully diluted shares
Total compensation target: $600,000 - $1,100,000

Bonus Structure
Executive bonuses are determined by a combination of company performance (60% weight) and individual performance (40% weight). Company performance metrics include revenue growth, ARR targets, customer retention rate, and product milestones. Individual performance is assessed by the board compensation committee.

Severance Policy
Executives are entitled to 6-12 months of severance upon involuntary termination without cause, with full acceleration of unvested equity in the case of a change-of-control event (double-trigger acceleration).""",
    },
]


def generate_mock_embedding(dimensions: int = 1536) -> List[float]:
    """Generate a random unit vector to use as a mock embedding.

    Produces a normalized random vector that mimics the structure
    of a real embedding without calling the OpenAI API.

    Args:
        dimensions: Vector dimensionality (default 1536).

    Returns:
        List of floats representing a normalized random vector.
    """
    raw = [random.gauss(0, 1) for _ in range(dimensions)]
    magnitude = sum(x * x for x in raw) ** 0.5
    return [x / magnitude for x in raw]


async def seed_users(db: AsyncSession) -> dict[str, uuid.UUID]:
    """Create seed users if they don't already exist.

    Returns:
        Mapping of email → user UUID.
    """
    user_ids: dict[str, uuid.UUID] = {}

    for user_data in SEED_USERS:
        result = await db.execute(
            select(User).where(User.email == user_data["email"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info("User %s already exists, skipping", user_data["email"])
            user_ids[user_data["email"]] = existing.id
            continue

        user = User(
            email=user_data["email"],
            password_hash=hash_password(user_data["password"]),
            full_name=user_data["full_name"],
            role=user_data["role"],
            is_active=True,
        )
        db.add(user)
        await db.flush()
        user_ids[user_data["email"]] = user.id
        logger.info(
            "Created user: %s (%s)", user_data["email"], user_data["role"]
        )

    await db.commit()
    return user_ids


async def seed_documents(
    db: AsyncSession,
    admin_id: uuid.UUID,
    mock_embeddings: bool = False,
) -> None:
    """Create seed documents, chunk them, and generate embeddings.

    Args:
        db: Async database session.
        admin_id: UUID of the admin user (document uploader).
        mock_embeddings: If True, use random vectors instead of OpenAI API.
    """
    for doc_data in SEED_DOCUMENTS:
        # Check if document already exists
        result = await db.execute(
            select(Document).where(Document.title == doc_data["title"])
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info("Document '%s' already exists, skipping", doc_data["title"])
            continue

        content = doc_data["content"]

        # Create document record
        doc = Document(
            title=doc_data["title"],
            filename=doc_data["filename"],
            file_size_bytes=len(content.encode("utf-8")),
            access_level=doc_data["access_level"],
            processing_status="processing",
            uploaded_by=admin_id,
        )
        db.add(doc)
        await db.flush()

        logger.info(
            "Processing document: '%s' (access: %s)",
            doc_data["title"],
            doc_data["access_level"],
        )

        # Chunk the document
        chunks = chunk_document(content)
        logger.info("  Chunked into %d chunks", len(chunks))

        # Generate embeddings
        if mock_embeddings:
            logger.info("  Using mock embeddings (random vectors)")
            embeddings = [generate_mock_embedding() for _ in chunks]
        else:
            from app.services.embedding_service import generate_embeddings_batch

            logger.info("  Generating real embeddings via OpenAI API...")
            texts = [c["content"] for c in chunks]
            embeddings = await generate_embeddings_batch(texts)

        # Store chunks with embeddings
        for chunk_data, embedding in zip(chunks, embeddings):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk_data["chunk_index"],
                content=chunk_data["content"],
                token_count=chunk_data["token_count"],
                embedding=embedding,
                access_level=doc_data["access_level"],
            )
            db.add(chunk)

        # Update document status
        doc.processing_status = "completed"
        doc.total_chunks = len(chunks)

        await db.flush()
        logger.info(
            "  Completed: %d chunks stored for '%s'",
            len(chunks),
            doc_data["title"],
        )

    await db.commit()


async def main(mock_embeddings: bool = False) -> None:
    """Run the full seed process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("DocuQuery AI — Database Seed Script")
    logger.info("=" * 60)

    if mock_embeddings:
        logger.info("Mode: MOCK EMBEDDINGS (random vectors)")
    else:
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "your-key-here":
            logger.error(
                "OPENAI_API_KEY is not set. Use --mock-embeddings for demo "
                "without an API key, or set the OPENAI_API_KEY environment variable."
            )
            sys.exit(1)
        logger.info("Mode: REAL EMBEDDINGS (OpenAI API)")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    async with async_session_factory() as db:
        # Seed users
        logger.info("--- Seeding Users ---")
        user_ids = await seed_users(db)

        admin_id = user_ids["admin@docuquery.ai"]

        # Seed documents
        logger.info("--- Seeding Documents ---")
        await seed_documents(db, admin_id, mock_embeddings=mock_embeddings)

    logger.info("=" * 60)
    logger.info("Seed complete!")
    logger.info("")
    logger.info("Demo accounts:")
    logger.info("  admin@docuquery.ai    / password123  (admin)")
    logger.info("  manager@docuquery.ai  / password123  (manager)")
    logger.info("  employee@docuquery.ai / password123  (employee)")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed the DocuQuery AI database with demo data."
    )
    parser.add_argument(
        "--mock-embeddings",
        action="store_true",
        default=False,
        help=(
            "Use random 1536-dim vectors instead of calling the OpenAI API. "
            "Allows running the demo without an OPENAI_API_KEY."
        ),
    )
    args = parser.parse_args()

    asyncio.run(main(mock_embeddings=args.mock_embeddings))
