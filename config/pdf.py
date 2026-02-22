from django.http import HttpResponse
from django.template.loader import render_to_string

def render_pdf_response(request, template_name: str, context: dict, filename: str):
    """
    WeasyPrint: HTML(template) -> PDF response
    """
    from weasyprint import HTML

    html = render_to_string(template_name, context=context, request=request)

    # base_url нужен для статики/картинок (если будете добавлять логотипы)
    base_url = request.build_absolute_uri("/")
    pdf_bytes = HTML(string=html, base_url=base_url).write_pdf()

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp