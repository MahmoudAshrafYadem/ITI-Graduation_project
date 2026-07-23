"""Streamlit Chat UI for Telecom RAG Assistant"""
import streamlit as st
from app.rag import TelecomRAG

# --- Page Config ---
st.set_page_config(
    page_title="Telecom RAG Assistant",
    page_icon="📡",
    layout="wide"
)

# --- Cache RAG Pipeline Initialization ---
# This ensures the models and DB are loaded only once, not on every interaction.
@st.cache_resource
def get_rag_pipeline():
    print("Loading RAG Pipeline...")
    return TelecomRAG()

# --- Initialize Session State for Chat History ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Sidebar for Filters ---
with st.sidebar:
    st.header("🔎 Search Filters")
    st.write("Limit the search to specific specs.")
    
    ts_filter = st.text_input("TS Number (e.g., 36.331)", "")
    release_filter = st.text_input("Release (e.g., 17)", "")
    
    st.divider()
    st.write("⚠️ **Note:** First question takes a few seconds as the AI models load.")
    
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# --- Main UI ---
st.title("📡 Telecom RAG Assistant")
st.caption("Ask engineering questions directly from 3GPP Specifications.")

# Initialize pipeline
try:
    rag = get_rag_pipeline()
except Exception as e:
    st.error(f"Failed to initialize AI models. Error: {e}")
    st.stop()

# Display Chat History
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Display references if they exist
        if message.get("references"):
            with st.expander(f"📖 View Citations ({len(message['references'])})"):
                for ref in message["references"]:
                    st.write(f"- **TS {ref['ts']}** | Release {ref['release']} | Section {ref['section']} | Page {ref['page']} _(Score: {ref['score']:.4f})_")

# Handle User Input
if prompt := st.chat_input("e.g., Explain Event A3 in LTE"):
    # Display User Message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display Assistant Response
    with st.chat_message("assistant"):
        with st.spinner("Searching 3GPP specifications and analyzing context..."):
            try:
                # Call the RAG pipeline
                response = rag.ask(
                    question=prompt,
                    ts_filter=ts_filter if ts_filter else None,
                    release_filter=release_filter if release_filter else None
                )
                
                answer = response["answer"]
                refs = response["references"]
                
                # Render the answer
                st.markdown(answer)
                
                # Render references immediately
                if refs:
                    with st.expander(f"📖 View Citations ({len(refs)})"):
                        for ref in refs:
                            st.write(f"- **TS {ref['ts']}** | Release {ref['release']} | Section {ref['section']} | Page {ref['page']} _(Score: {ref['score']:.4f})_")
                            
                # Save to history
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "references": refs
                })
                
            except Exception as e:
                st.error(f"An error occurred: {e}")