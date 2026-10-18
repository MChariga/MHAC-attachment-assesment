"""Builds the KoboToolbox XLSForm (MHAC_Attachment_Assessment_Kobo_Form.xlsx).
Usage: pip install openpyxl && python build_xlsform.py
Edit the `sections` / `students` lists below to change questions or the class list."""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

sections = [
 ("soil","Soil health",[
  "Keep soil covered with plant or mulch","Practice contour planting on steep land",
  "Control water surface runoff where erosion is high","Composting plant and animal manure",
  "Student has identified the soil in his area (soil profile)",
  "Capture and use livestock urine in composting and residue management","Manage compost quality",
  "Recycling of farm and kitchen residue","Make bokashi",
  "Made liquid manure (manure tea, tithonia tea etc)","Manage striga using residue-based intervention"]),
 ("pest","Pest management",[
  "Do the crops look healthy","Disposal of infested plants (sanitary field condition in composting area)",
  "Use of plant residue for composting","Crop diversification, intercropping and companion planting",
  "Have they planted tephrosia, aloe vera etc. in their farm",
  "Use of push and pull technologies (extra points)","Planting of flowers to attract beneficial insects",
  "Use of Tephrosia, ash brew, chili etc to manage and control pest"]),
 ("lvst","Livestock",[
  "Considers provision of animal nutritional needs in farm planning - Fodder crops, trees, pastures, cereals, tubers, and farm by-products",
  "Has planted resilient grasses, pasture, and legumes based on the Agroecological zone",
  "Makes fermented livestock feeds following GO, GROW, GLOW needs",
  "Has planned and conserved fodder for the livestock for use during the dry season. Made silage, hay, and standing forage in the field (Brachiaria, Panicum maximum, stover)",
  "Understands animal welfare principles and is visible on the farm",
  "Hygiene and comfort in the livestock living areas (is the place clean?)",
  "Proactive internal and external parasite control - Use of botanical remedies i.e. Tephrosia powder, aloe vera, papaya leaves, chili, ginger, turmeric",
  "Follow biosecurity strategies - footbaths, fencing of livestock units",
  "Proper feeding and mineral supplementation of livestock",
  "Provide clean water to the livestock throughout"]),
 ("nutr","Family nutrition",[
  "Consider provision of family nutritional needs in farm planning",
  "Have they grown any alternative crops in their garden","Grows diverse vegetables in the farm",
  "Grow diverse carbohydrate plants in the farm (maize, sweet potatoes, cassava, bananas etc)",
  "Grow diverse protein crops in the farm (soya, beans, lablab etc)",
  "Grow and manage fruit trees in the homestead",
  "Initiative of starting small livestock projects (rabbits, poultry, guinea pigs) to manage family nutrition",
  "Produced crops for income generation","Added value to surplus farm produce if any",
  "Method of storage and packaging of value added product if any","Sold any value added product if any"]),
 ("agro","Agroforestry and food forest",[
  "Started a small tree nursery at home","Planted agroforestry trees in the farm (diverse trees)",
  "Manage trees in the farm","Managed a tree nursery at home","Harvested and propagated seed at home",
  "Practiced vegetative propagation of tree at home",
  "Planted herbs, spices and medicinal plants e.g. aloe vera, mints etc"]),
 ("tech","Appropriate technologies",[
  "Use of locally available resources to solve immediate challenges",
  "Implemented small gardening technologies (raised beds, bag gardens, mandala gardens etc)",
  "Involved neighbours in their work and neighbours have started adopting agroecology",
  "Irrigation methods used"]),
 ("clim","Climate change strategies",[
  "Water harvesting strategies in the farm (micro catchment e.g. zai pits, sunken beds)",
  "Grown resilient crops (drought tolerant)"]),
 ("watr","Water management",[
  "Dug directional channels","Dug banana circles",
  "Planted diverse food in swales, bunds",
  "Demonstrated slowing, sinking, and spreading water"]),
]

# The class list is personal data, so it is NOT stored in this file or in the repository.
# Put it in roster.csv (columns: reg,name) in the project root. That file is git-ignored.
import csv, pathlib, sys
_roster = pathlib.Path(__file__).resolve().parent.parent / "roster.csv"
if not _roster.exists():
    sys.exit("Missing roster.csv in the project root (columns: reg,name). See README.")
with open(_roster, newline="", encoding="utf-8-sig") as _f:
    students = [(r["reg"].strip(), r["name"].strip()) for r in csv.DictReader(_f) if r.get("reg")]

cols = ["type","name","label","media::image","hint","required","appearance","relevant","constraint","constraint_message","calculation","default"]
rows=[]
FONT="font-family:\'Palatino Linotype\',Palatino,\'Book Antiqua\',serif"
def add(**k):
    l=k.get("label")
    if l and l.strip() and not l.startswith("<span"):
        k["label"]='<span style="%s">%s</span>' % (FONT, l)
    rows.append(k)

for t in ("start","end","deviceid"): add(type=t,name=t)
GREEN='#2E7D32'
def green(t): return '<span style="color:%s;%s">%s</span>' % (GREEN, FONT, t)
add(type="begin_group",name="g_intro",label="",appearance="field-list")
add(type="note",name="n_logo",label=" ")
rows[-1]["media::image"]="mhac_logo.png"
add(type="note",name="n_addr",label=green("Manor House Agricultural Centre")+"\n\n"+green("P.O Box Private Bag, Kitale (30200)")+"\n\n"+green("+254 722 744 927 / +254 731 483 793")+"\n\n"+green("mhac@africaonline.co.ke"))
add(type="note",name="n_t1",label=green("**Attachment Assessment Tool**"))
add(type="note",name="n_t2",label=green("Training Department"))
add(type="date",name="assess_date",label="Date of assessment",required="yes",default="today()")
add(type="select_one assessors",name="assessor",label="Name of assessor",required="yes",appearance="minimal")
add(type="select_one students",name="reg_no",label="Name of student",required="yes",appearance="minimal")
add(type="calculate",name="student_name",calculation="jr:choice-name(${reg_no}, '${reg_no}')")
add(type="note",name="n_adm",label="Admission No: ${reg_no}",relevant="${reg_no} != ''")
add(type="text",name="organization",label="Name of organization",required="yes")
add(type="text",name="place",label="Place of attachment",required="yes")
add(type="text",name="village",label="Community/village",required="yes")
add(type="end_group",name="")

for sid,title,qs in sections:
    add(type="begin_group",name=f"g_{sid}",label=green("**"+title+"**"),appearance="table-list field-list")
    for i,q in enumerate(qs,1):
        add(type="select_one rating",name=f"{sid}_{i:02d}",label=f"_{i}. {q}_",required="yes",
            appearance=("" if i==1 else "list-nolabel") or None)
    add(type="end_group",name="")

HINT="One entry per box. If there is more than one, answer Yes to 'Add another' below to get another box."
MAXN=10
add(type="begin_group",name="g_final",label=green("**Major challenges and supervisor's remarks**"),appearance="field-list")
def chain(pref,label,one,hint):
    add(type="text",name=f"{pref}_1",label=f"{label} 1",hint=hint,appearance="multiline")
    for k in range(2,MAXN+1):
        add(type="select_one yesno",name=f"{pref}_add_{k}",label=f"Add another {one}?",appearance="minimal",
            relevant="${%s_%d} != ''" % (pref,k-1))
        add(type="text",name=f"{pref}_{k}",label=f"{label} {k}",appearance="multiline",
            relevant="${%s_add_%d} = 'yes'" % (pref,k))
chain("challenge","Challenge","challenge",HINT)
chain("comment","Supervisor's comment","comment",HINT)
add(type="text",name="sup_name",label="Name of supervisor",required="yes")
add(type="text",name="sup_designation",label="Designation",required="yes")
add(type="date",name="sup_date",label="Date",default="today()")
add(type="end_group",name="")

wb=Workbook(); ws=wb.active; ws.title="survey"
ws.append(cols)
for r in rows: ws.append([r.get(c) for c in cols])
ch=wb.create_sheet("choices"); ch.append(["list_name","name","label"])
for n in ("Kelvin Kenbun","Denis Mbori","Andrew Simotwo"): ch.append(["assessors",n.lower().replace(" ","_"),n])
for reg,n in students: ch.append(["students",reg,n])
for n,l in (("yes","Yes"),("no","No")): ch.append(["yesno",n,l])
for n,l in (("poor","0-2 Poor"),("good","3-4 Good"),("very_good","5-6 Very Good"),("na","Not applicable")): ch.append(["rating",n,l])
st=wb.create_sheet("settings"); st.append(["form_title","form_id","version","default_language","style"])
st.append(["Manor House – Attachment Assessment Tool","mhac_attachment_assessment_2026a","2026101607","English (en)","pages"])
for w in wb.worksheets:
    for c in w[1]: c.font=Font(bold=True,color="FFFFFF"); c.fill=PatternFill("solid",fgColor="2E7D32")
    w.freeze_panes="A2"
    for col,width in zip("ABCDEFGHIJKL",(26,26,70,18,20,10,16,34,60,40,60,12)): w.column_dimensions[col].width=width
wb.save(Path(__file__).parent / "MHAC_Attachment_Assessment_Kobo_Form.xlsx")
print(len(rows))
