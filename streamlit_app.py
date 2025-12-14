import streamlit as st
from openai import OpenAI
import json
import os
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from PyPDF2 import PdfReader
import io

# 페이지 설정
st.set_page_config(
    page_title="인사 서류 안내 챗봇",
    page_icon="📋",
    layout="centered",
)

# 세션 상태 초기화 (가장 먼저)
if "admin_mode" not in st.session_state:
    st.session_state.admin_mode = False
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "안녕하세요! 육아휴직이나 4대보험 피부양자 등록과 관련하여 필요한 서류를 안내해드립니다. 어떤 것이 궁금하신가요?",
        }
    ]

st.title("📋 인사 서류 안내 챗봇")
st.caption("육아휴직 및 4대보험 피부양자 등록 관련 서류를 안내해드립니다.")

# OpenAI 클라이언트 초기화
@st.cache_resource
def get_openai_client():
    try:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    except Exception:
        st.error("OPENAI_API_KEY가 secrets.toml에 설정되어 있지 않습니다.")
        st.stop()

client = get_openai_client()

# Firebase 초기화
@st.cache_resource
def get_firestore_client():
    """Firebase Firestore 클라이언트 초기화"""
    if not firebase_admin._apps:
        # secrets.toml에서 Firebase 설정 읽기
        firebase_config = dict(st.secrets["firebase"])
        cred = credentials.Certificate(firebase_config)
        
        # storage bucket 설정
        project_id = firebase_config.get('project_id')
        firebase_admin.initialize_app(cred, {
            'storageBucket': f"{project_id}.firebasestorage.app"
        })
    
    return firestore.client()

db = get_firestore_client()

# 로그 파일 경로 (로컬 백업용)
LOG_FILE = "chat_logs.json"

# 로그 저장 함수
def save_log(user_query: str, bot_response: str):
    """사용자 질문과 봇 응답을 Firestore에 저장"""
    log_entry = {
        "timestamp": datetime.now(),
        "query": user_query,
        "response": bot_response
    }
    
    try:
        # Firestore에 저장
        db.collection('chat_logs').add(log_entry)
        
        # 로컬 백업도 저장
        logs = []
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    logs = json.load(f)
                except:
                    logs = []
        
        log_entry_json = {
            "timestamp": log_entry["timestamp"].isoformat(),
            "query": user_query,
            "response": bot_response
        }
        logs.append(log_entry_json)
        
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"로그 저장 실패: {e}")

# 로그 읽기 함수
def load_logs():
    """Firestore에서 저장된 모든 로그 읽기"""
    try:
        # Firestore에서 읽기 (최신순 정렬)
        logs_ref = db.collection('chat_logs').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(100)
        docs = logs_ref.stream()
        
        logs = []
        for doc in docs:
            data = doc.to_dict()
            logs.append({
                'id': doc.id,
                'timestamp': data['timestamp'].isoformat() if hasattr(data['timestamp'], 'isoformat') else str(data['timestamp']),
                'query': data['query'],
                'response': data['response']
            })
        
        return logs
    except Exception as e:
        st.error(f"로그 읽기 실패: {e}")
        # 실패 시 로컬 파일에서 읽기
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []

# PDF 관련 함수
def extract_text_from_pdf(pdf_file):
    """PDF 파일에서 텍스트 추출"""
    try:
        pdf_reader = PdfReader(io.BytesIO(pdf_file.read()))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        st.error(f"PDF 텍스트 추출 실패: {e}")
        return None

def save_document_to_firestore(doc_name: str, content: str):
    """규정 문서를 Firestore에 저장"""
    try:
        doc_data = {
            "name": doc_name,
            "content": content,
            "uploaded_at": datetime.now(),
            "active": True
        }
        db.collection('documents').document(doc_name).set(doc_data)
        return True
    except Exception as e:
        st.error(f"문서 저장 실패: {e}")
        return False

def load_documents_from_firestore():
    """Firestore에서 활성화된 규정 문서들 로드"""
    try:
        docs_ref = db.collection('documents').where('active', '==', True).stream()
        documents = []
        for doc in docs_ref:
            data = doc.to_dict()
            documents.append({
                'name': data.get('name', 'Unknown'),
                'content': data.get('content', ''),
                'uploaded_at': data.get('uploaded_at', '')
            })
        return documents
    except Exception as e:
        st.error(f"문서 로드 실패: {e}")
        return []

def delete_document_from_firestore(doc_name: str):
    """Firestore에서 문서 삭제"""
    try:
        db.collection('documents').document(doc_name).delete()
        return True
    except Exception as e:
        st.error(f"문서 삭제 실패: {e}")
        return False

# 자주 묻는 질문 정의
FAQ_QUESTIONS = [
    "4대보험 피부양자 등록을 하려면 어떤 서류를 제출해야 하나요?",
    "육아휴직 신청 시 제출해야 할 서류는 무엇인가요?",
    "육아휴직 1년 사용 후 6개월 연장 시 필요한 서류는 무엇인가요?",
    "육아휴직 급여를 얼마나 받을 수 있나요?",
    "출산휴가 후 육아휴직 바로 전환하려면 어떻게 하나요?",
]

# 시스템 프롬프트 생성 함수
def build_system_prompt():
    """Firestore에서 규정 문서를 가져와 시스템 프롬프트 생성"""
    base_prompt = """당신은 인사 서류 제출을 안내하는 친절한 HR 어시스턴트입니다.

주요 안내 사항:

**육아휴직 급여 신청을 위한 자녀 정보 제출 안내:**
- 공문으로 육아휴직 신청서 제출 시 자녀 주민등록번호 뒷자리가 기재된 가족관계증명서를 첨부해 주세요.
- 개인정보인 주민등록번호 공문 첨부가 우려되면 HR 담당자 이메일로 별도 송부해 주세요.
- 육아휴직 급여 지급을 위한 신청서 제출 시 자녀 주민등록번호 확인이 필요합니다(고용센터 필수 확인사항).
- 산전 휴직이면 자녀 주민번호를 알 수 없으므로 해당 없음.

**1년 육아휴직 사용 후 연장 신청 시 추가 증빙 안내:**
- 육아휴직 급여 대상기간은 1년이며, 부부가 모두 육아휴직을 사용하는 경우에 한해 1년 6개월까지 지급됩니다.
- 최초 1년 사용 후 추가 6개월 연장 시, 배우자가 동시에 3개월 이상 육아휴직을 사용했다는 증빙자료를 제출해 주세요. 없으면 제출 불필요.
- 배우자가 동시에 3개월 이상 육아휴직을 사용했다는 증빙자료:
  * 같은 자녀를 대상으로 부모가 모두 육아휴직을 각각 3개월 이상 사용한 경우의 부 또는 모
  * 증빙자료 예시: ▲육아휴직급여 지급 결정 통지서, ▲회사에서 공식적으로 발령한 휴직-복직 발령문(휴직 발령문만으로는 실제 휴직여부를 알 수 없으므로 복직 발령문도 함께 확인 필요)

**육아휴직 신청 시 기본 필요 서류:**
1. 육아휴직 신청서
2. 가족관계증명서 (주민등록번호 뒷자리 포함)

**출산휴가 후 육아휴직 바로 전환:**
- 통합신청서를 제출하면 됩니다.
- 통합신청서 작성 항목:
  1. 신청인의 성명, 생년월일 등 인적사항
  2. 육아휴직 대상인 영유아의 성명·생년월일
  3. 휴직개시예정일
  4. 육아휴직을 종료하려는 날
  5. 육아휴직 신청 연월일
  6. 출산전후휴가 또는 배우자출산휴가 개시예정일 및 종료일(통합신청시에만 기재)
- 자세한 내용은 링크 참고: https://www.moel.go.kr/news/notice/noticeView.do?bbs_seq=20250100161

**4대보험 피부양자 등록 시 필요 서류:**
- 피부양자 명의의 가족관계증명서 (주민등록번호 뒷자리 포함), 제출처는 회사 인사부서 담당자.

**추가 참고 사항:**
- 가족관계증명서는 주민센터 또는 정부24에서 발급 가능합니다.
- 주민등록번호 뒷자리가 포함되어야 합니다.
- 발급일로부터 3개월 이내 서류를 제출해야 합니다.

**육아휴직 급여 관련:**
- 육아휴직급여는 고용보험에 가입해 있는 피보험자가 받을 수 있습니다.
- 미리 알아보는 나의 육아휴직급여 지급액 모의계산: https://www.work24.go.kr/cm/c/f/1100/selecSimulate12.do?currentPageNo=1&recordCountPerPage=10&upprSystClId=SC00000245&systClId=SC00000251&systId=SI00000402&systCnntId=CI00001626
- 육아휴직급여에 관한 급여모의계산은 고용보험에 가입해 있는 피보험자가 육아휴직급여를 받게될 경우 받게 될 육아휴직급여를 계산해 볼 수 있습니다.
"""
    
    # Firestore에서 업로드된 규정 문서 가져오기
    documents = load_documents_from_firestore()
    
    if documents:
        base_prompt += "\n\n**=== 추가 규정 및 안내 사항 (관리자 업로드) ===**\n\n"
        for doc in documents:
            base_prompt += f"**[{doc['name']}]**\n{doc['content']}\n\n"
    
    base_prompt += "\n사용자의 질문에 따라 필요한 서류를 명확하고 친절하게 안내하세요. 단계별로 설명하고, 추가 궁금한 사항을 묻습니다."
    
    return base_prompt

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "안녕하세요! 육아휴직이나 4대보험 피부양자 등록과 관련하여 필요한 서류를 안내해드립니다. 어떤 것이 궁금하신가요?",
        }
    ]
if "admin_mode" not in st.session_state:
    st.session_state.admin_mode = False

# 대화 히스토리 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# FAQ에서 추가된 질문이 있으면 AI 응답 생성
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_message = st.session_state.messages[-1]
    # 이미 응답이 생성되지 않은 경우에만 응답 생성
    needs_response = True
    if len(st.session_state.messages) >= 2:
        if st.session_state.messages[-2]["role"] == "assistant":
            # 이전 메시지가 assistant이면 새로운 user 메시지에 대한 응답 필요
            needs_response = True
    
    if needs_response and last_message["content"] in FAQ_QUESTIONS:
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            try:
                # 동적으로 시스템 프롬프트 생성
                system_prompt = build_system_prompt()
                messages_for_api = [{"role": "system", "content": system_prompt}] + st.session_state.messages
                stream = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages_for_api,
                    stream=True,
                    temperature=0.7,
                    max_tokens=1000,
                )

                for chunk in stream:
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        full_response += delta
                        placeholder.markdown(full_response + "▌")
                placeholder.markdown(full_response)
            except Exception as e:
                full_response = f"오류가 발생했습니다: {e}"
                placeholder.error(full_response)

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        # 로그 저장
        save_log(last_message["content"], full_response)
        st.rerun()

# 사용자 입력 처리
if prompt := st.chat_input("질문을 입력하세요..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = ""

        try:
            # 동적으로 시스템 프롬프트 생성
            system_prompt = build_system_prompt()
            messages_for_api = [{"role": "system", "content": system_prompt}] + st.session_state.messages
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                stream=True,
                temperature=0.7,
                max_tokens=1000,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    full_response += delta
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            full_response = f"오류가 발생했습니다: {e}"
            placeholder.error(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    # 로그 저장
    save_log(prompt, full_response)

# 관리자 모드 페이지 (맨 아래)
if st.session_state.admin_mode:
    st.divider()
    st.subheader("🔐 관리자 모드")
    
    # 탭으로 구분
    tab1, tab2 = st.tabs(["📊 검색 이력", "📄 규정 관리"])
    
    with tab1:
        logs = load_logs()
        
        if logs:
            st.info(f"총 {len(logs)}개의 검색 기록이 있습니다.")
            
            # 통계
            col1, col2 = st.columns(2)
            with col1:
                st.metric("총 검색 수", len(logs))
            
            # 로그 표시
            st.subheader("📊 검색 이력")
            
            for i, log in enumerate(reversed(logs), 1):
                with st.expander(f"{i}. {log['query'][:50]}... ({log['timestamp'][:10]})"):
                    st.markdown("**사용자 질문:**")
                    st.write(log['query'])
                    st.markdown("**챗봇 답변:**")
                    st.write(log['response'])
                    st.caption(f"시간: {log['timestamp']}")
            
            # 로그 다운로드
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                log_json = json.dumps(logs, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 로그 다운로드 (JSON)",
                    log_json,
                    "chat_logs.json",
                    "application/json"
                )
            
            with col2:
                if st.button("🗑️ 모든 로그 삭제", type="secondary"):
                    os.remove(LOG_FILE)
                    st.success("로그가 삭제되었습니다.")
                    st.rerun()
        else:
            st.info("아직 검색 기록이 없습니다.")
    
    with tab2:
        st.subheader("📄 규정 문서 관리")
        
        # PDF 업로드
        st.markdown("### 📤 새 규정 문서 업로드")
        uploaded_pdf = st.file_uploader(
            "PDF 파일을 업로드하세요",
            type=["pdf"],
            help="업로드한 PDF 내용이 챗봇 답변에 자동으로 반영됩니다."
        )
        
        if uploaded_pdf:
            doc_name = st.text_input("문서 이름", value=uploaded_pdf.name.replace(".pdf", ""))
            
            if st.button("📤 업로드 및 저장", type="primary"):
                with st.spinner("PDF에서 텍스트 추출 중..."):
                    pdf_text = extract_text_from_pdf(uploaded_pdf)
                    
                    if pdf_text:
                        if save_document_to_firestore(doc_name, pdf_text):
                            st.success(f"✅ '{doc_name}' 문서가 저장되었습니다!")
                            st.rerun()
                        else:
                            st.error("문서 저장에 실패했습니다.")
                    else:
                        st.error("PDF에서 텍스트를 추출할 수 없습니다.")
        
        # 현재 저장된 문서 목록
        st.divider()
        st.markdown("### 📚 저장된 규정 문서")
        
        documents = load_documents_from_firestore()
        
        if documents:
            for doc in documents:
                with st.expander(f"📄 {doc['name']}"):
                    st.caption(f"업로드: {doc.get('uploaded_at', 'N/A')}")
                    st.text_area(
                        "문서 내용",
                        value=doc['content'][:500] + "..." if len(doc['content']) > 500 else doc['content'],
                        height=200,
                        disabled=True,
                        key=f"doc_{doc['name']}"
                    )
                    
                    if st.button(f"🗑️ 삭제", key=f"del_{doc['name']}", type="secondary"):
                        if delete_document_from_firestore(doc['name']):
                            st.success(f"'{doc['name']}' 문서가 삭제되었습니다.")
                            st.rerun()
        else:
            st.info("아직 업로드된 규정 문서가 없습니다.")

# 사이드바에 안내 정보 추가
with st.sidebar:
    st.header("📌 주요 안내")
    
    st.markdown("### 자주 묻는 질문")
    st.caption("질문을 클릭하면 챗봇이 답변해드립니다.")
    
    for i, question in enumerate(FAQ_QUESTIONS, 1):
        if st.button(f"Q{i}: {question}", key=f"faq_{i}", use_container_width=True):
            # FAQ 질문을 채팅에 추가
            st.session_state.messages.append({"role": "user", "content": question})
            st.rerun()

    st.divider()
    
    if st.button("대화 초기화", type="secondary", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "안녕하세요! 육아휴직이나 4대보험 피부양자 등록과 관련하여 필요한 서류를 안내해드립니다. 어떤 것이 궁금하신가요?",
            }
        ]
        st.rerun()
    
    st.divider()
    
    # 관리자 로그인
    st.markdown("### 🔑 관리자")
    if not st.session_state.admin_mode:
        admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_pwd")
        if admin_password and st.button("로그인"):
            if admin_password == st.secrets.get("ADMIN_PASSWORD", "admin123"):
                st.session_state.admin_mode = True
                st.success("관리자 모드 활성화!")
                st.rerun()
            else:
                st.error("비밀번호가 틀렸습니다.")
    else:
        st.success("✅ 관리자 모드 활성화")
        if st.button("로그아웃"):
            st.session_state.admin_mode = False
            st.rerun()
