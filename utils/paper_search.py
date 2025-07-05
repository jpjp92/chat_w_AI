import requests
import arxiv
import xml.etree.ElementTree as ET
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

logger = logging.getLogger(__name__)

class PaperSearchAPI:
    def __init__(self, ncbi_key, cache_handler, cache_ttl=3600):
        self.ncbi_key = ncbi_key
        self.cache = cache_handler
        self.cache_ttl = cache_ttl
        self.pubmed_base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    
    def fetch_arxiv_paper(self, paper):
        """ArXiv 논문 정보를 추출합니다."""
        return {
            "title": paper.title,
            "authors": ", ".join(str(a) for a in paper.authors),
            "summary": paper.summary[:200],
            "entry_id": paper.entry_id,
            "pdf_url": paper.pdf_url,
            "published": paper.published.strftime('%Y-%m-%d')
        }
    
    def get_arxiv_papers(self, query, max_results=3):
        """ArXiv에서 논문을 검색합니다."""
        cache_key = f"arxiv:{query}:{max_results}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            search = arxiv.Search(
                query=query, 
                max_results=max_results, 
                sort_by=arxiv.SortCriterion.SubmittedDate
            )
            
            with ThreadPoolExecutor() as executor:
                results = list(executor.map(self.fetch_arxiv_paper, search.results()))
            
            if not results:
                return "해당 키워드로 논문을 찾을 수 없습니다."
            
            response = "📚 **Arxiv 논문 검색 결과** 📚\n\n"
            response += "\n\n".join([
                f"**논문 {i}**\n\n"
                f"📄 **제목**: {r['title']}\n\n"
                f"👥 **저자**: {r['authors']}\n\n"
                f"📝 **초록**: {r['summary']}...\n\n"
                f"🔗 **논문 페이지**: {r['entry_id']}\n\n"
                f"📅 **출판일**: {r['published']}"
                for i, r in enumerate(results, 1)
            ]) + "\n\n더 궁금한 점 있나요? 😊"
            
            self.cache.setex(cache_key, self.cache_ttl, response)
            return response
            
        except Exception as e:
            logger.error(f"ArXiv 검색 오류: {str(e)}")
            return "ArXiv 논문 검색 중 오류가 발생했습니다. 😓"
    
    def search_pubmed(self, query, max_results=5):
        """PubMed에서 논문 ID를 검색합니다."""
        search_url = f"{self.pubmed_base_url}esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "api_key": self.ncbi_key
        }
        response = requests.get(search_url, params=params, timeout=3)
        return response.json()
    
    def get_pubmed_summaries(self, id_list):
        """PubMed 논문 요약 정보를 가져옵니다."""
        summary_url = f"{self.pubmed_base_url}esummary.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "json",
            "api_key": self.ncbi_key
        }
        response = requests.get(summary_url, params=params, timeout=3)
        return response.json()
    
    def get_pubmed_abstract(self, id_list):
        """PubMed 논문 초록을 가져옵니다."""
        fetch_url = f"{self.pubmed_base_url}efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
            "api_key": self.ncbi_key
        }
        response = requests.get(fetch_url, params=params, timeout=3)
        return response.text
    
    def extract_first_two_sentences(self, abstract_text):
        """초록에서 첫 두 문장을 추출합니다."""
        if not abstract_text or abstract_text.isspace():
            return "No abstract available"
        sentences = [s.strip() for s in abstract_text.split('.') if s.strip()]
        return " ".join(sentences[:2]) + "." if sentences else "No abstract available"
    
    def parse_abstracts(self, xml_text):
        """XML에서 초록을 파싱합니다."""
        abstract_dict = {}
        try:
            root = ET.fromstring(xml_text)
            for article in root.findall(".//PubmedArticle"):
                pmid = article.find(".//MedlineCitation/PMID").text
                abstract_elem = article.find(".//Abstract/AbstractText")
                abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
                abstract_dict[pmid] = self.extract_first_two_sentences(abstract)
        except ET.ParseError:
            return {}
        return abstract_dict
    
    def format_date(self, fordate):
        """날짜 형식을 통일합니다."""
        if fordate == 'No date':
            return '날짜 없음'
        try:
            date_obj = datetime.strptime(fordate, '%Y %b %d')
            return date_obj.strftime('%Y.%m.%d')
        except ValueError:
            return fordate
    
    def get_pubmed_papers(self, query, max_results=5):
        """PubMed에서 논문을 검색합니다."""
        cache_key = f"pubmed:{query}:{max_results}"
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        try:
            search_results = self.search_pubmed(query, max_results)
            pubmed_ids = search_results["esearchresult"]["idlist"]
            
            if not pubmed_ids:
                return "해당 키워드로 의학 논문을 찾을 수 없습니다."
            
            summaries = self.get_pubmed_summaries(pubmed_ids)
            abstracts_xml = self.get_pubmed_abstract(pubmed_ids)
            abstract_dict = self.parse_abstracts(abstracts_xml)
            
            response = "🩺 **PubMed 논문 검색 결과** 🩺\n\n"
            response += "\n\n".join([
                f"**논문 {i}**\n\n"
                f"🆔 **PMID**: {pmid}\n\n"
                f"📖 **제목**: {summaries['result'][pmid].get('title', 'No title')}\n\n"
                f"📅 **출판일**: {self.format_date(summaries['result'][pmid].get('pubdate', 'No date'))}\n\n"
                f"✍️ **저자**: {', '.join([author.get('name', '') for author in summaries['result'][pmid].get('authors', [])])}\n\n"
                f"📝 **초록**: {abstract_dict.get(pmid, 'No abstract')}\n\n"
                f"🔗 **논문 페이지**: https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                for i, pmid in enumerate(pubmed_ids, 1)
            ]) + "\n\n더 궁금한 점 있나요? 😊"
            
            self.cache.setex(cache_key, self.cache_ttl, response)
            return response
            
        except Exception as e:
            logger.error(f"PubMed 검색 오류: {str(e)}")
            return "PubMed 논문 검색 중 오류가 발생했습니다. 😓"