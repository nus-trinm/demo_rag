"""Create sample policy PDFs and DOCX files; no company data is used."""
from pathlib import Path
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

root = Path(__file__).resolve().parent.parent / 'sample_docs'
root.mkdir(exist_ok=True)
policies = {
 'remote_old.docx': ('Remote Work Policy v1', ['Employees may work remotely one day per week with manager approval.', 'This policy applies to Acme employees.']),
 'remote_current.docx': ('Remote Work Policy v2', ['Acme employees may work remotely up to three days per week with manager approval.', 'Employees must protect confidential information while working remotely.']),
 'annual_leave.docx': ('Annual Leave Policy', ['Acme employees receive 18 days of annual leave per calendar year.', 'Employees must request leave through the HR system at least two weeks in advance.']),
 'travel.pdf': ('Travel Expenses Policy', ['Acme reimburses reasonable business travel expenses when employees submit receipts within 30 days.', 'Personal travel and entertainment expenses are not reimbursable.']),
 'northstar.docx': ('Northstar Remote Work Policy', ['Northstar employees may work remotely five days per week with manager approval.', 'This policy applies only to Northstar employees.']),
}
for filename, (title, paragraphs) in policies.items():
    path = root / filename
    if path.suffix == '.docx':
        d = Document(); d.add_heading(title,0)
        for p in paragraphs: d.add_paragraph(p)
        d.save(path)
    else:
        c=canvas.Canvas(str(path)); y=800
        for paragraph in [title,*paragraphs]:
            for line in simpleSplit(paragraph,'Helvetica',11,490): c.drawString(50,y,line); y-=18
            y-=15
        c.save()
    print(path)
