# Jugaad GPT

**Product Description  
CMPT 370 · University of Saskatchewan**

## Section 1: Project Details

**Group Name:**  "We'll Study It Later"     
**Teaching Assistant:** Palash

| # | Name | Email | NSID |
|---|------|-------|------|
| 1 | Patel Aarya | pcq713@usask.ca | pcq713 |
| 2 | Patel Haryan | bwr045@usask.ca | bwr045 |
| 3 | Patel Hetank | fjw827@usask.ca | fjw827 |
| 4 | Sawant Mohit | cwf024@usask.ca | cwf024 |
| 5 | Patel Priyesh | orv018@usask.ca | orv018 |

## Section 2: Product Description

**Product Name:** Jugaad GPT

**Product Description:**
A web application that answers questions about USask campus life housing, dining, clubs, recreation, health services, transit, and safety; using a knowledge base built from public university web pages.

**Essential features:**
- Plain language question entry
- Retrieval over indexed page content
- Answers generated only from the retrieved passages
- A source link on every answer
- An explicit refusal when no passage matches well enough
- A maintainer view for adding and refreshing sources

**Need and Value:**
Campus life information is spread across many separate USask pages and is difficult to locate, particularly for first year and international students. General AI assistants answer such questions confidently but have limited access of USask pages in front of them, so they can sometime give wrong information like deadlines, fees, and procedures. Jugaad GPT differs by answering only from real pages, showing the source so the student can verify it, and declining to answer rather than guessing a wrong answer about a deadline or a fee, which is worse than no answer, because students act on it.

***Stakeholders:***
- **Students** are the primary users, especially those new to campus.
- A **maintainer** organise the content and refreshes the sources.
- **University units** whose information the product relays to the user (Student Central, Residence, the USSU, and Recreation Services) will not use the system themselves but have an interest in whether it represents their policies accurately.
- The **course instructor and teaching assistant** will assess the product.
- Our named **external stakeholder** is a USask student in the same degree who is not enrolled in this course.

**Technology Requirements:**
- **Development:** Python 3.10+, Git on git.cs.usask.ca, pytest for testing, and requests with Beautiful Soup for collecting page content.
- **Deployed product:** a retrieval index (BM25 initially, with sentence embeddings for semantic matching), an LLM API for answer generation, JSON storage for the page corpus, and a lightweight HTML/CSS/JavaScript front end.