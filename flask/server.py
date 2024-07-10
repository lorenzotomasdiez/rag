#!/usr/bin/env python
import os
import chromadb
import requests

from flask import Flask, request, jsonify
from pymongo import MongoClient
from markdown import markdown
from config import config
import uuid
import logging

app = Flask(__name__)

client = MongoClient("mongo:27017")
chroma_client = chromadb.Client()

collection = chroma_client.create_collection(name="documents")

logging.basicConfig(level=logging.DEBUG)

def load_markdown_files(directory):
    data = []
    for filename in os.listdir(directory):
        if filename.endswith(".md"):
            filepath = os.path.join(directory, filename)
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
                html_content = markdown(content)
                data.append({"filename": filename, "content": html_content})
                logging.debug(f"Loaded file: {filename}")
    return data

@app.route('/api/reindex', methods=['POST'])
def reindex():
    clean()
    try:
        markdown_data = load_markdown_files('local_files')
        for doc in markdown_data:
            doc_id = str(uuid.uuid4())  # Generar un ID único
            collection.add(ids=[doc_id], documents=[doc['content']], metadatas=[{"filename": doc['filename']}])
        return jsonify({"status": "success", "message": "Reindexing completed."})
    except Exception as e:
        logging.error(f"Error during reindexing: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/query', methods=['POST'])
def query():
    try:
        user_query = request.json.get('query')
        
        # Realizar búsqueda en ChromaDB
        logging.debug("Before results")
        results = collection.query(query_texts=[user_query], n_results=5)
        logging.debug("after results")
        
        # Depuración de resultados
        logging.debug(f"Results: {results}")
        
        # Preparar el prompt con los resultados
        prompt = f"{user_query}\n\n"
        for i in range(len(results['documents'][0])):
            filename = results['metadatas'][0][i]['filename']
            content = results['documents'][0][i]
            prompt += f"{filename}: {content}\n\n"
        
        logging.debug(f"Prompt: {prompt}")

        # Realizar solicitud a la instancia local de Ollama
        url = f"http://{config.OLLAMA_API_URL}/api/generate"
        payload = {
            "model": "llama3",
            "prompt": prompt,
            "stream":False
        }
        logging.debug(f"URL: {url}")
        logging.debug(f"Payload: {payload}")
        
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Esto lanzará una excepción si la respuesta no tiene un código de estado 2xx
        
        # Imprimir la respuesta en bruto
        logging.debug(f"Raw response: {response.text}")

        try:
            response_data = response.json()
            logging.debug(f"Ollama Response: {response_data}")
            return jsonify(response_data['response'].strip())
        except ValueError as e:
            logging.error(f"Error parsing response JSON: {e}")
            return jsonify({"status": "error", "message": "Error parsing response JSON"}), 500
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error during query: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    except Exception as e:
        logging.error(f"Error during query: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clean', methods=['POST'])
def clean():
    try:
        all_documents = collection.get()
        logging.debug(f"All documents: {all_documents}")

        # Asegúrate de que 'ids' está en all_documents y es una lista
        if 'ids' in all_documents and isinstance(all_documents['ids'], list):
            all_ids = all_documents['ids']
            logging.debug(f"All IDs to delete: {all_ids}")
            
            # Eliminar todos los documentos usando sus IDs
            collection.delete(ids=all_ids)
            return jsonify({"status": "success", "message": "Collection cleaned."})
        else:
            raise ValueError("No document IDs found in the collection.")
    except Exception as e:
        logging.error(f"Error during cleaning: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def todo():
    try:
        client.admin.command('ismaster')
    except:
        return "Server not available"
    return "Hello from the MongoDB client!\n"


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=os.environ.get("FLASK_SERVER_PORT", 9090), debug=True)