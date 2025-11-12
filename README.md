🛒 Retail Flyer Data Pipeline: Multimodal Extraction & Normalization

This repository contains the core scripts for an automated pipeline designed to find, download, and extract structured product and offer data from retail PDF flyers using the Google Gemini API.

The pipeline converts visual data (multi-page PDF flyers) into standardized, database-ready JSON format.

🏗️ System Architecture Overview

The system operates in two main stages:

Data Acquisition (Downloader): PDFs are gathered (e.g., via web scraping) and stored in a designated input directory.

Data Enrichment & Normalization (categorizer.py): The core engine processes these PDFs, converts them into high-resolution images, uses the Gemini API's multimodal and structured output capabilities to extract offers, and post-processes the data for consistency.

Flow: PDF Flyers ➡️ categorizer.py ➡️ Standardized JSON Data

🔬 Pipeline Components and Script Roles

This pipeline evolved through several stages, culminating in the robust categorizer.py script.

1. The Data Acquisition Script (Conceptual Downloader)

Role: Gathers and downloads new PDF flyers from various retailer sources (e.g., website scraping, email parsing).

Output: Stores new PDF files inside the ./downloads folder, using a structured naming convention (e.g., RETAILER_2025-10-22_SaleTitle.pdf) to enable date extraction later.

Current Status: This is a conceptual prerequisite step that ensures the categorizer.py script always has fresh data to work with.

2. Initial Extraction Drafts (Version 1 & 2)

Role: These early scripts focused on basic extraction using the Gemini API.

Limitations: They typically handled only single-page PDFs, lacked error handling for large files, and produced inconsistent output that required significant manual cleanup due to a lack of strict JSON schema enforcement. They served as critical proofs-of-concept to validate the multimodal approach.

Current Status: Obsolete. They have been superseded by the final, production-ready script.

3. Core Extraction and Normalization Script (categorizer.py)

Role: This is the production script responsible for processing, extracting, enriching, and normalizing the data from the PDF images.

Key Functions:

PDF to Image Conversion: Uses Poppler utilities to convert each PDF page into a high-DPI image.

Batch Processing: Automatically splits large, multi-page flyers into manageable batches for the Gemini API.

Structured Extraction: Enforces strict JSON schema and Category ENUMs to ensure every output object is valid and standardized.

Post-Processing: Cleans raw text data by converting prices to numbers, parsing dates, and generating stable, unique product hashes.

Logging: Maintains a log of processed files (processed_flyer_log.json) to prevent reprocessing and save costs.

🛠️ Prerequisites

To run the pipeline, you need the following dependencies and environment setup:

1. System Dependencies (Poppler)

The pdf2image library requires the Poppler utility suite to be installed on your operating system.

OS

Installation Command

Linux (Debian/Ubuntu)

sudo apt-get install poppler-utils

macOS (Homebrew)

brew install poppler

Windows

Download and add the bin path to your system's environment variables.

2. Python Dependencies

The script requires a few standard Python packages, including the official Google GenAI SDK.

pip install google-genai pypdf pdf2image python-dotenv


3. FLOW

leaflet_retrieval > leaflet_downloader > ocr_analyzer

lidl + spar >> data_enricher 

merge all resulting data



4. NEEDS WORK

ocr_analyzer, test the productHash, work out how this maakes sense and what the productHash should be, primarily for item unification, and image reusability
data enricher needs to generate productHash and search terms for the products that are scraped form these 2 retailers, and enrich them simialir to the ocr_analyzer, images are present here so need to be linked or renamed

merge all data and start creating a UI for this

Product Pipeline works 100%
Automation task for downloading leaflets and getting new ones works 100%


