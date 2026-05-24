# Mock Documents — Data Dictionary

These plain-text files simulate real enterprise documents for testing the
Document Intelligence app (LLM-powered Q&A over unstructured text).

---

## Files

### `expense_report_q1_2024.txt`
**Type:** Corporate expense report  
**Department:** Engineering — AI Platform  
**Period:** Q1 2024 (Jan 1 – Mar 31, 2024)  
**Total claimed:** $13,844.48  
**Sections:** Travel & Transportation | Software & Licenses | Training & Development | Equipment & Supplies  
**Status:** Pending CFO Review  

Suggested LLM prompts:
- "What is the total amount claimed in this expense report?"
- "List all software subscriptions and their annual costs."
- "Who has approved this report so far and what is the current status?"
- "Summarize the training expenses and their business justification."
- "Is this report over or under budget, and by how much?"

---

### `contract_sample_nda.txt`
**Type:** Mutual Non-Disclosure Agreement  
**Parties:** Fidelity Institutional / Vertex Analytics Inc.  
**Effective Date:** March 1, 2024  
**Purpose:** Evaluation of AI data analytics platform integration  
**Term:** 3 years from effective date  
**Governing Law:** Texas  

Suggested LLM prompts:
- "What is the purpose of this agreement?"
- "How long does the confidentiality obligation last after termination?"
- "What are the exclusions from the definition of Confidential Information?"
- "What remedies are available if Confidential Information is misused?"
- "Summarize the key obligations of the Receiving Party."
- "What happens to confidential materials when the agreement ends?"

---

### `invoice_vendor_xyz.txt`
**Type:** Vendor invoice  
**Vendor:** CloudScale Solutions Inc. (Austin, TX)  
**Client:** Fidelity Institutional (Accounts Payable)  
**Invoice #:** CSI-2024-03-0089  
**Invoice Date:** March 31, 2024  
**Due Date:** April 30, 2024  
**Subtotal:** $1,254.79 | **Tax (8.25%):** $103.52 | **Total Due:** $1,358.31  
**Services:** EC2 compute, S3 storage, RDS PostgreSQL, CloudFront CDN, Premium Support, Managed Backup  

Suggested LLM prompts:
- "What is the total amount due and when is the payment deadline?"
- "List all AWS services billed and their individual costs."
- "What are the payment options available for this invoice?"
- "What is the late payment policy?"
- "Which line item is the most expensive?"

---

## Usage in Code

```python
from shared.utils import load_document, list_documents

# List available documents
docs = list_documents()

# Load a specific document
text = load_document("contract_sample_nda.txt")

# Pass to LLM
from shared.llm_client import llm
answer = llm.query_with_context(
    prompt="What are the payment terms?",
    context=text,
    system_message="You are a contract review assistant. Answer based only on the document provided."
)
```
