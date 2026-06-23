
# chatbot/views_test.py
from django.http import JsonResponse
import google.generativeai as genai
import os

def gemini_simple_test(request):
    """ Completely isolated test - does not affect chatbot """
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        return JsonResponse({"error": "GEMINI_API_KEY not found in environment variables"}, status=500)
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        response = model.generate_content("Say hello in one short sentence.")
        
        return JsonResponse({
            "status": "success",
            "gemini_response": response.text.strip(),
            "api_key_present": True
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)
