"""
Host Machine Test Script
Run this on the machine running Docker to verify containers are working.

Usage:
    cd infra
    python test_host.py
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("test_host")

DOCLING_URL = "http://localhost:5001"
PDFFIGURES_URL = "http://localhost:5002"


async def test_docling():
    import httpx
    
    logger.info("Testing Docling at %s", DOCLING_URL)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{DOCLING_URL}/health")
            logger.info("  Health check: %d", resp.status_code)
            if resp.status_code != 200:
                return False
        except Exception as e:
            logger.error("  Health check failed: %s", e)
            return False
        
        test_url = "https://arxiv.org/pdf/2301.13379"
        logger.info("  Parsing test PDF: %s", test_url)
        
        try:
            resp = await client.post(
                f"{DOCLING_URL}/v1/convert/source",
                json={
                    "sources": [{"kind": "http", "url": test_url}],
                    "output_formats": ["markdown"],
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            
            md_content = data.get("document", {}).get("md_content", "") or ""
            if md_content:
                logger.info("  ✓ Docling working! Got %d chars", len(md_content))
                return True
            else:
                logger.warning("  ✗ Docling returned empty content")
                return False
        except Exception as e:
            logger.error("  ✗ Docling parsing failed: %s", e)
            return False


async def test_pdffigures():
    import httpx
    
    logger.info("Testing PDFFigures at %s", PDFFIGURES_URL)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{PDFFIGURES_URL}/health")
            logger.info("  Health check: %d", resp.status_code)
            if resp.status_code != 200:
                return False
        except Exception as e:
            logger.error("  Health check failed: %s", e)
            return False
        
        test_url = "https://arxiv.org/pdf/2301.13379"
        logger.info("  Downloading test PDF: %s", test_url)
        
        try:
            pdf_resp = await client.get(test_url, follow_redirects=True)
            pdf_resp.raise_for_status()
            logger.info("  Downloaded %d bytes", len(pdf_resp.content))
            
            logger.info("  Extracting figures...")
            resp = await client.post(
                f"{PDFFIGURES_URL}/extract",
                files={"file": ("paper.pdf", pdf_resp.content, "application/pdf")},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            
            inner = data.get("data", data)
            figures = inner.get("figures", [])
            logger.info("  ✓ PDFFigures working! Found %d figures", len(figures))
            return True
        except Exception as e:
            logger.error("  ✗ PDFFigures extraction failed: %s", e)
            return False


async def main():
    logger.info("=" * 60)
    logger.info("Host Machine Container Test")
    logger.info("=" * 60)
    logger.info("")
    
    docling_ok = await test_docling()
    logger.info("")
    pdffigures_ok = await test_pdffigures()
    
    logger.info("")
    logger.info("=" * 60)
    if docling_ok and pdffigures_ok:
        logger.info("All containers working correctly!")
    else:
        logger.warning("Some containers failed - check docker logs")
        if not docling_ok:
            logger.warning("  - Docling: docker logs trace-docling-1")
        if not pdffigures_ok:
            logger.warning("  - PDFFigures: docker logs trace-pdffigures-1")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())


