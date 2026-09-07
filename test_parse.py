"""
Test script for Paper Parsing (Docling + PDFFigures 2.0)

Usage:
    # Start both services:
    cd infra && docker-compose up -d docling pdffigures
    
    # Run test:
    python test_parse.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_parse")


async def check_services():
    import httpx
    
    services = {
        "Docling": "http://localhost:5001/health",
        "PDFFigures": "http://localhost:4567/",
    }
    
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services.items():
            try:
                resp = await client.get(url)
                logger.info("✓ %s is running (status %d)", name, resp.status_code)
                results[name] = True
            except Exception as e:
                logger.warning("✗ %s is not running: %s", name, e)
                results[name] = False
    return results


async def test_docling_only():
    from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
    
    agent = PaperRetrievalAgent()
    
    test_url = "https://arxiv.org/pdf/1706.03762"
    logger.info("Testing Docling PDF parsing from: %s", test_url)
    
    try:
        docling_result = await agent._parse_with_docling(test_url)
        logger.info("✓ Docling parsed successfully!")
        logger.info("  Title: %s", docling_result.title[:80])
        logger.info("  Authors: %s", ", ".join(docling_result.authors[:3]))
        logger.info("  Sections: %d", len(docling_result.sections))
        logger.info("  References: %d", len(docling_result.references))
        logger.info("  Full text length: %d chars", len(docling_result.full_text))
        return True
    except Exception as e:
        logger.error("✗ Docling parsing failed: %s", e)
        return False


async def test_with_database():
    from apps.api.services import db_service
    from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
    
    agent = PaperRetrievalAgent()
    
    result = db_service.supabase.table("retrieved_papers").select("id").limit(1).execute()
    
    if not result.data:
        logger.warning("No papers in retrieved_papers table. Inserting test paper...")
        
        test_paper = {
            "query_id": "test-query-id",
            "title": "Attention Is All You Need",
            "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "year": 2017,
            "source": "arxiv",
            "arxiv_id": "1706.03762",
        }
        
        db_result = db_service.supabase.table("retrieved_papers").insert(test_paper).execute()
        paper_id = db_result.data[0]["id"]
        logger.info("Inserted test paper with ID: %s", paper_id)
    else:
        paper_id = result.data[0]["id"]
        logger.info("Using existing paper ID: %s", paper_id)
    
    logger.info("Parsing paper %s...", paper_id)
    parsed = await agent.parse_papers([paper_id])
    
    if parsed:
        paper = parsed[0]
        logger.info("✓ Parsing successful!")
        logger.info("  Title: %s", paper.title)
        logger.info("  Authors: %s", ", ".join(paper.authors[:3]))
        logger.info("  Sections: %d", len(paper.sections))
        logger.info("  References: %d", len(paper.references))
        logger.info("  Figures: %d", len(paper.figures))
        logger.info("  Full text length: %d chars", len(paper.full_text))
        
        db_result = db_service.supabase.table("parsed_papers").select("*").eq("retrieved_paper_id", paper_id).execute()
        if db_result.data:
            logger.info("✓ Stored in parsed_papers table")
        else:
            logger.error("✗ Not found in parsed_papers table")
    else:
        logger.error("✗ Parsing failed")
    
    return bool(parsed)


async def main():
    logger.info("=" * 60)
    logger.info("Paper Parser Test (Docling + PDFFigures)")
    logger.info("=" * 60)
    
    logger.info("\n1. Checking services...")
    service_status = await check_services()
    
    if not service_status.get("Docling"):
        logger.warning("Docling not running - paper parsing won't work")
    if not service_status.get("PDFFigures"):
        logger.warning("PDFFigures not running - figures won't be extracted")
    
    logger.info("\n2. Testing Docling parsing (no database)...")
    try:
        await test_docling_only()
    except Exception as e:
        logger.error("Docling test failed: %s", e)
    
    logger.info("\n3. Testing database integration...")
    try:
        await test_with_database()
    except Exception as e:
        logger.error("Database test failed: %s", e)
    
    logger.info("\n" + "=" * 60)
    logger.info("Tests complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
