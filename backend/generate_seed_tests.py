"""Generate seed_tests.csv with all ~197 standard lab tests."""

import csv
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "seed_tests.csv"
COLUMNS = ["test_name", "test_method", "test_category", "default_unit", "default_specification"]


def build_test_list() -> list[dict]:
    tests: list[dict] = []

    def add(name: str, method: str, category: str, unit: str, spec: str) -> None:
        tests.append({
            "test_name": name,
            "test_method": method,
            "test_category": category,
            "default_unit": unit,
            "default_specification": spec,
        })

    # ── MICROBIOLOGICAL (39) ────────────────────────────────────────────
    add("Total Plate Count", "AOAC 990.12", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Total Plate Count (USP <2021>)", "USP <2021>", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Rapid Aerobic Plate Count", "AOAC 2015.13", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Yeast & Mold", "AOAC 2014.05", "Microbiological", "CFU/g", "< 1,000 CFU/g")
    add("Yeast & Mold (USP <2021>)", "USP <2021>", "Microbiological", "CFU/g", "< 1,000 CFU/g")
    add("Total Coliform Count", "AOAC 991.14", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Total Coliform Count (USP <2021>)", "USP <2021> modified", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Total E. coli Count", "AOAC 991.14", "Microbiological", "CFU/g", "< 10 CFU/g")
    add("Total Enterobacteriaceae Count", "AOAC 2003.01", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Total Enterobacteriaceae Count (USP <2021>)", "USP <2021> modified", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Escherichia coli", "AOAC-RI 050601", "Microbiological", "Present/Absent", "Negative")
    add("Escherichia coli (USP <2022>)", "USP <2022>", "Microbiological", "Present/Absent", "Absent")
    add("Coliform", "AOAC-RI 050601", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("E. coli O157:H7", "AOAC-RI 090501", "Microbiological", "Present/Absent", "Negative")
    add("Salmonella spp.", "AOAC 020502", "Microbiological", "Present/Absent", "Negative")
    add("Salmonella spp. (USP <2022>)", "USP <2022>", "Microbiological", "Present/Absent", "Negative")
    add("Staphylococcus aureus", "AOAC-RI 100503", "Microbiological", "Present/Absent", "Negative")
    add("Staphylococcus aureus (USP <2022>)", "USP <2022>", "Microbiological", "Present/Absent", "Negative")
    add("Pseudomonas aeruginosa", "USP <62>", "Microbiological", "Present/Absent", "Absent")
    add("Listeria monocytogenes", "AFNOR AES 10/03-09/00", "Microbiological", "Present/Absent", "Negative")
    add("Listeria spp.", "AFNOR AES 10/03-09/00", "Microbiological", "Present/Absent", "Negative")
    add("Burkholderia cepacia complex", "USP <60>", "Microbiological", "Present/Absent", "Absent")
    add("Bile-Tolerant Gram-Negative Bacteria", "USP <2021>", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Clostridium spp.", "USP <2022>", "Microbiological", "Present/Absent", "Absent")
    add("Candida albicans", "USP <62>", "Microbiological", "Present/Absent", "Absent")
    add("Total Contaminating Microorganisms", "ISO 13559", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Total Anaerobic Plate Count", "CMMEF 5th 6.7", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Total Lactic Acid Bacteria Count", "CMMEF 5th 19.52", "Microbiological", "CFU/g", "Report")
    add("Heterotrophic Plate Count", "SM 9215", "Microbiological", "CFU/mL", "< 500 CFU/mL")
    add("Bacillus cereus", "DL 1.02", "Microbiological", "Present/Absent", "Negative")
    add("Total Bacillus cereus", "DL 1.02", "Microbiological", "CFU/g", "< 10,000 CFU/g")
    add("Escherichia coli (SMEWW)", "SMEWW 9223", "Microbiological", "MPN/100mL", "Absent")
    add("Fecal Coliform", "SMEWW 9223", "Microbiological", "MPN/100mL", "< 1 MPN/100mL")
    add("Coliform (SMEWW)", "SMEWW 9223", "Microbiological", "MPN/100mL", "< 1 MPN/100mL")
    add("Total Coliform (FDA-BAM)", "FDA-BAM Ch 4", "Microbiological", "MPN/g", "< 100 MPN/g")
    add("Total E. coli (FDA-BAM)", "FDA-BAM Ch 4", "Microbiological", "MPN/g", "< 10 MPN/g")
    add("Enterococcus spp.", "DL 1.02", "Microbiological", "Present/Absent", "Negative")
    add("Total Enterococcus Count", "DL 1.02", "Microbiological", "CFU/g", "< 100 CFU/g")
    add("Total Legionella spp.", "CDC Legionella", "Microbiological", "CFU/L", "Negative")

    # ── HEAVY METALS (22) ───────────────────────────────────────────────
    add("Heavy Metals Panel (As, Cd, Hg, Pb)", "ICP-MS", "Heavy Metals", "ppm", "As < 1.5, Cd < 0.5, Pb < 0.5, Hg < 0.2")
    add("Arsenic", "ICP-MS", "Heavy Metals", "ppm", "< 1.5 ppm")
    add("Cadmium", "ICP-MS", "Heavy Metals", "ppm", "< 0.5 ppm")
    add("Lead", "ICP-MS", "Heavy Metals", "ppm", "< 0.5 ppm")
    add("Mercury", "ICP-MS", "Heavy Metals", "ppm", "< 0.2 ppm")
    for metal in [
        "Aluminum", "Antimony", "Barium", "Beryllium", "Chromium", "Cobalt",
        "Copper", "Gallium", "Lithium", "Manganese", "Nickel", "Selenium",
        "Silver", "Strontium", "Thallium", "Uranium", "Vanadium",
    ]:
        add(metal, "ICP-MS", "Heavy Metals", "ppm", "Report")

    # ── ALLERGENS (18) ──────────────────────────────────────────────────
    add("Gluten", "AOAC-RI 061403", "Allergens", "ppm", "< 20 ppm")
    for allergen in [
        "Soy", "Milk", "Egg", "Almond", "Beta-Lactoglobulin", "Brazil Nut",
        "Casein", "Cashew/Pistachio", "Coconut", "Crustacea", "Hazelnut",
        "Lupin", "Macadamia", "Mustard", "Peanut", "Sesame", "Walnut",
    ]:
        add(allergen, "Test Strip", "Allergens", "Pos/Neg", "Negative")

    # ── NUTRITIONAL (12) ────────────────────────────────────────────────
    add("Protein", "AOAC 990.03", "Nutritional", "%", "Report")
    add("Fat", "AOAC 922.06", "Nutritional", "%", "Report")
    add("Moisture", "AOAC 930.15", "Nutritional", "%", "Report")
    add("Ash", "AOAC 923.03", "Nutritional", "%", "Report")
    add("Carbohydrates", "Calculation", "Nutritional", "%", "Report")
    add("Solids", "Gravimetric", "Nutritional", "%", "Report")
    for mineral in ["Calcium", "Iron", "Magnesium", "Potassium", "Sodium", "Zinc"]:
        add(mineral, "ICP-MS", "Nutritional", "mg/g", "Per label claim")

    # ── CHEMICAL (38) ───────────────────────────────────────────────────
    add("Total Chlorine", "Hach CN-70", "Chemical", "ppm", "Report")
    add("Aflatoxins", "LC-MS/MS", "Chemical", "ppb", "< 20 ppb")
    add("Aflatoxins + Ochratoxin", "LC-MS/MS", "Chemical", "ppb", "< 20 ppb each")
    add("Ochratoxin", "LC-MS/MS", "Chemical", "ppb", "< 20 ppb")
    add("Patulin", "LC-MS/MS", "Chemical", "ppb", "< 50 ppb")
    add("Red 40 (Allura Red)", "HPLC", "Chemical", "ppm", "Report")
    add("FD&C Blue #1", "HPLC", "Chemical", "ppm", "Report")
    add("FD&C Yellow #6", "HPLC", "Chemical", "ppm", "Report")
    add("Diacetyl", "GC-MS", "Chemical", "ppm", "Report")
    add("Ethanol", "GC-FID", "Chemical", "%", "Report")
    add("Glycerol", "HPLC", "Chemical", "%", "Report")
    add("Organic acids (acetic & citric)", "HPLC", "Chemical", "%", "Report")
    add("Vanillin", "HPLC", "Chemical", "ppm", "Report")
    add("Acrylamide", "LC-MS/MS", "Chemical", "ppb", "Report")
    add("Biogenic amines (panel of 4)", "HPLC", "Chemical", "ppm", "Report")
    add("Biogenic amines (panel of 8)", "HPLC", "Chemical", "ppm", "Report")
    add("Cellulose", "Gravimetric", "Chemical", "%", "Report")
    add("Ethyl acetate", "GC-FID", "Chemical", "ppm", "< 5,000 ppm")
    add("Methanol", "GC-FID", "Chemical", "ppm", "< 3,000 ppm")
    add("Residual solvent panel", "USP <467>", "Chemical", "ppm", "Conforms to USP <467>")
    add("Smoke taint testing", "GC-MS", "Chemical", "ppb", "Report")
    add("Starch (Qualitative)", "Iodine Test", "Chemical", "Pos/Neg", "Report")
    add("Starch (Quantitative)", "Enzymatic", "Chemical", "%", "Report")
    add("Peroxide Value", "AOCS Cd 8-53", "Chemical", "meq O2/kg", "< 10 meq O2/kg")
    add("Titratable acidity", "Titration", "Chemical", "%", "Report")
    add("Free fatty acids", "AOCS Ca 5a-40", "Chemical", "%", "Report")
    add("Chloride", "Ion Chromatography", "Chemical", "ppm", "Report")
    add("Preservative panel (3-comp)", "HPLC", "Chemical", "ppm", "Report")
    add("Preservative panel (2-comp)", "HPLC", "Chemical", "ppm", "Report")
    add("Nitrite", "Colorimetric", "Chemical", "ppm", "< 200 ppm")
    add("Sulfite", "LC-MS/MS", "Chemical", "ppm", "< 10 ppm")
    add("Artificial sweeteners", "HPLC", "Chemical", "ppm", "Report")
    add("Lactose", "HPLC", "Chemical", "%", "Report")
    add("Sucrose", "HPLC", "Chemical", "%", "Report")
    add("Sugar profile", "HPLC", "Chemical", "%", "Report")
    add("Nitrates", "Ion Chromatography", "Chemical", "ppm", "< 10 ppm")
    add("Phosphates", "Ion Chromatography", "Chemical", "ppm", "Report")
    add("Chlorine (Water)", "DPD Colorimetric", "Chemical", "ppm", "Report")

    # ── PHYSICAL (4) ────────────────────────────────────────────────────
    add("pH", "USP <791>", "Physical", "pH", "Report")
    add("Water Activity", "Dew Point", "Physical", "aw", "< 0.6 aw")
    add("Bulk Density", "USP <616>", "Physical", "g/mL", "Report")
    add("Brix", "Refractometry", "Physical", "Brix", "Report")

    # ── POTENCY - AMINO ACIDS (23) ──────────────────────────────────────
    amino_acids = [
        "N-acetyl L-Tyrosine", "N-acetyl L-Carnitine", "N-acetyl L-Cysteine",
        "BCAAs (Leucine Isoleucine Valine)", "Beta-alanine", "Betaine",
        "Carnitine", "Creatine", "L-Arginine", "L-Arginine AKG",
        "L-Aspartic acid", "L-Citrulline", "L-Citrulline Malate",
        "L-Glutamine", "L-Glycine", "L-Isoleucine", "L-Leucine",
        "L-Methionine", "L-Phenylalanine", "L-Proline", "L-Threonine",
        "L-Tyrosine", "L-Valine",
    ]
    for aa in amino_acids:
        add(aa, "HPLC", "Potency - Amino Acids", "mg/g", "Per label claim")

    # ── POTENCY - VITAMINS (16) ─────────────────────────────────────────
    vitamins = [
        ("Thiamin (B1)", "mg/g"),
        ("Riboflavin (B2)", "mg/g"),
        ("Niacinamide (B3)", "mg/g"),
        ("Pantothenic acid (B5)", "mg/g"),
        ("Pyridoxine HCl (B6)", "mg/g"),
        ("Folic acid (B9)", "mcg/g"),
        ("Cyanocobalamin (B12)", "mcg/g"),
        ("Mecobalamin (B12)", "mcg/g"),
        ("Vitamin A (Beta-Carotene)", "IU/g"),
        ("Vitamin A (Retinol)", "IU/g"),
        ("Vitamin C (ascorbic acid)", "mg/g"),
        ("Vitamin D", "IU/g"),
        ("Vitamin E", "IU/g"),
        ("Vitamin K1 (synthetic)", "mcg/g"),
        ("Vitamin K3 (synthetic)", "mcg/g"),
        ("Vitamin K (naturally derived)", "mcg/g"),
    ]
    for name, unit in vitamins:
        add(name, "HPLC", "Potency - Vitamins", unit, "Per label claim")

    # ── POTENCY - SUPPLEMENTS (22) ──────────────────────────────────────
    supplements = [
        ("5HTP", "HPLC", "mg/g"),
        ("Alpha Lipoic Acid", "HPLC", "mg/g"),
        ("Ashwagandha", "HPLC", "%"),
        ("Berberine", "HPLC", "mg/g"),
        ("Bioperine", "HPLC", "mg/g"),
        ("Butyric Acid", "GC-FID", "mg/g"),
        ("DHEA", "HPLC", "mg/g"),
        ("Ginkgo biloba", "HPLC", "%"),
        ("Ginseng", "HPLC", "%"),
        ("Glucoraphanin", "HPLC", "mg/g"),
        ("Glutathione (reduced)", "HPLC", "mg/g"),
        ("Melatonin", "HPLC", "mg/g"),
        ("MSM", "HPLC", "mg/g"),
        ("NMN", "HPLC", "mg/g"),
        ("Polydatin", "HPLC", "mg/g"),
        ("Polydatin & Resveratrol", "HPLC", "mg/g"),
        ("Resveratrol", "HPLC", "mg/g"),
        ("S-Acetyl Glutathione", "HPLC", "mg/g"),
        ("SAMe", "HPLC", "mg/g"),
        ("Sulforaphane", "HPLC", "mg/g"),
        ("Turmeric", "HPLC", "%"),
        ("Zingerone", "HPLC", "mg/g"),
    ]
    for name, method, unit in supplements:
        add(name, method, "Potency - Supplements", unit, "Per label claim")

    # ── POTENCY - OTHER (9) ─────────────────────────────────────────────
    potency_other = [
        ("Caffeine", "HPLC", "mg/g"),
        ("Taurine", "HPLC", "mg/g"),
        ("Theanine", "HPLC", "mg/g"),
        ("Theobromine", "HPLC", "mg/g"),
        ("Glucuronolactone", "HPLC", "mg/g"),
        ("Stevia glycosides", "HPLC", "%"),
        ("Cannabinoids", "HPLC", "%"),
        ("Kratom Potency (HPLC)", "HPLC", "%"),
        ("Kratom Potency (LC-MS/MS)", "LC-MS/MS", "%"),
    ]
    for name, method, unit in potency_other:
        add(name, method, "Potency - Other", unit, "Per label claim")

    # ── POTENCY - FLAVONOIDS (15) ───────────────────────────────────────
    flavonoids = [
        "Apigenin", "Cyanidin", "Delphinidin", "Kaempferol", "Luteolin",
        "Orientin", "Peonidin", "Quercetin", "Rutin", "Silybin",
        "Vitexin", "Xanthohumol", "3-O-beta-Rutinoside",
        "7-O-beta-Glucoside", "Flavonoid panel",
    ]
    for name in flavonoids:
        add(name, "HPLC", "Potency - Flavonoids", "mg/g", "Per label claim")

    # ── POTENCY - TERPENES (14) ─────────────────────────────────────────
    terpenes = [
        "Camphene", "Carvacrol", "beta-Caryophyllene", "alpha-Cedrene",
        "Eucalyptol", "Geraniol", "Guaiol", "delta-Limonene", "Linalool",
        "Menthol", "Nerolidol", "Ocimene", "alpha-Pinene", "beta-Pinene",
    ]
    for name in terpenes:
        add(name, "GC-MS", "Potency - Terpenes", "%", "Per label claim")

    # ── COMPLIANCE (3) ──────────────────────────────────────────────────
    add("Amazon Weight Loss Panel", "Amazon Banned Substances", "Compliance", "Pass/Fail", "Pass")
    add("Amazon Sexual Enhancement Panel", "Amazon Banned Substances", "Compliance", "Pass/Fail", "Pass")
    add("Amazon Sports Nutrition Panel", "Amazon Banned Substances", "Compliance", "Pass/Fail", "Pass")

    return tests


def main() -> None:
    tests = build_test_list()

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(tests)

    # Print summary by category
    from collections import Counter
    counts = Counter(t["test_category"] for t in tests)
    for category, count in sorted(counts.items()):
        print(f"  {category}: {count}")
    print(f"\nTotal tests written to {OUTPUT_PATH}: {len(tests)}")


if __name__ == "__main__":
    main()
