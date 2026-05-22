"""
GlowCheck – Sample Data Seeder
Seeds 30 realistic US cosmetic products with ingredients and EWG scores.
Run once:  python seed_data.py
"""

import os
import json
from database import get_db, init_db, DB_PATH

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db()

INGREDIENTS = [
    # id will be auto-assigned; keyed by name for linking
    # (name, inci_name, ewg_score, function, description)
    ("Water",               "Aqua",                          1, "Solvent",              "Primary solvent in most formulas."),
    ("Glycerin",            "Glycerin",                      1, "Humectant",            "Draws moisture from air into skin."),
    ("Niacinamide",         "Niacinamide",                   1, "Brightening, Barrier", "Reduces pore appearance, evens tone, strengthens barrier."),
    ("Hyaluronic Acid",     "Sodium Hyaluronate",            1, "Humectant",            "Holds up to 1000× its weight in water."),
    ("Retinol",             "Retinol",                       5, "Anti-aging",           "Speeds cell turnover; reduce wrinkles & acne."),
    ("Vitamin C",           "Ascorbic Acid",                 1, "Antioxidant",          "Brightens, protects from free radicals."),
    ("Salicylic Acid",      "Salicylic Acid",                3, "Exfoliant, Acne",      "Oil-soluble BHA that unclogs pores."),
    ("Benzoyl Peroxide",    "Benzoyl Peroxide",              6, "Acne",                 "Kills acne-causing bacteria."),
    ("Zinc Oxide",          "Zinc Oxide",                    1, "UV Filter, Soothing",  "Mineral SPF with soothing properties."),
    ("Titanium Dioxide",    "Titanium Dioxide",              1, "UV Filter",            "Mineral broad-spectrum UV protection."),
    ("Dimethicone",         "Dimethicone",                   1, "Silicone, Emollient",  "Provides slip, fills fine lines temporarily."),
    ("Cetearyl Alcohol",    "Cetearyl Alcohol",              1, "Emulsifier",           "Fatty alcohol; moisturizing, not drying."),
    ("Shea Butter",         "Butyrospermum Parkii",          1, "Emollient",            "Rich butter that deeply moisturizes."),
    ("Jojoba Oil",          "Simmondsia Chinensis",          1, "Emollient",            "Mimics skin's natural sebum."),
    ("Squalane",            "Squalane",                      1, "Emollient",            "Lightweight oil from olives or sugarcane."),
    ("Lactic Acid",         "Lactic Acid",                   1, "AHA Exfoliant",        "Gentle AHA that smooths and hydrates."),
    ("Azelaic Acid",        "Azelaic Acid",                  1, "Brightening, Acne",    "Reduces redness and hyperpigmentation."),
    ("Ceramide NP",         "Ceramide NP",                   1, "Barrier",              "Key lipid that repairs skin barrier."),
    ("Panthenol",           "Panthenol",                     1, "Humectant, Healing",   "Pro-vitamin B5; soothes and heals."),
    ("Allantoin",           "Allantoin",                     1, "Soothing",             "Gentle calming ingredient."),
    ("Aloe Vera",           "Aloe Barbadensis",              1, "Soothing, Hydrating",  "Classic soothing & cooling botanical."),
    ("Green Tea Extract",   "Camellia Sinensis",             1, "Antioxidant",          "Polyphenol-rich; protects from oxidative stress."),
    ("Vitamin E",           "Tocopherol",                    1, "Antioxidant",          "Fat-soluble antioxidant; pairs with Vitamin C."),
    ("Caffeine",            "Caffeine",                      1, "Antioxidant, Depuff",  "Reduces puffiness; antioxidant."),
    ("Phenoxyethanol",      "Phenoxyethanol",                4, "Preservative",         "Common preservative; safe at <1%."),
    ("Fragrance",           "Parfum",                        8, "Fragrance",            "Undisclosed mix; common allergen."),
    ("Mineral Oil",         "Paraffinum Liquidum",           2, "Emollient",            "Occlusive that locks in moisture."),
    ("Talc",                "Talc",                          3, "Filler, Absorbent",    "Soft mineral powder in many makeups."),
    ("Mica",                "Mica",                          1, "Colorant, Shimmer",    "Natural mineral that gives shimmer."),
    ("Iron Oxides",         "Iron Oxides (CI 77491)",        1, "Colorant",             "Mineral pigments for foundation/blush shades."),
    ("Alcohol Denat",       "Alcohol Denatured",             6, "Solvent",              "Drying at high concentrations."),
    ("Oxybenzone",          "Benzophenone-3",                8, "Chemical UV Filter",   "Controversial chemical sunscreen; hormone concern."),
    ("Avobenzone",          "Butyl Methoxydibenzoylmethane", 5, "Chemical UV Filter",   "UVA filter; degrades in UV light."),
    ("Peptides",            "Palmitoyl Tripeptide-1",        1, "Anti-aging",           "Signal proteins that stimulate collagen."),
    ("Kojic Acid",          "Kojic Acid",                    2, "Brightening",          "Melanin inhibitor from fungi."),
    ("Alpha Arbutin",       "Alpha-Arbutin",                 1, "Brightening",          "Gentle melanin inhibitor."),
    ("Ferulic Acid",        "Ferulic Acid",                  1, "Antioxidant",          "Boosts stability of Vitamins C & E."),
    ("Centella Asiatica",   "Centella Asiatica Extract",     1, "Soothing, Healing",    "Calming botanical for sensitive skin."),
    ("Colloidal Oatmeal",   "Avena Sativa",                  1, "Soothing",             "FDA-approved skin protectant."),
    ("BHA",                    "Butylated Hydroxyanisole",          8, "Preservative",         "Antioxidant preservative; possible carcinogen concern."),
    # --- Concern-related & Hair ingredients ---
    ("Sodium Lauryl Sulfate",  "Sodium Lauryl Sulfate",             7, "Surfactant",           "Harsh foaming agent; strips scalp/skin barrier."),
    ("Sodium Laureth Sulfate", "Sodium Laureth Sulfate",            3, "Surfactant",           "Milder than SLS; common shampoo cleanser."),
    ("Ammonium Lauryl Sulfate","Ammonium Lauryl Sulfate",           7, "Surfactant",           "Sulfate detergent; can irritate sensitive scalps."),
    ("Cocamidopropyl Betaine", "Cocamidopropyl Betaine",            4, "Surfactant",           "Amphoteric cleanser; potential sensitizer."),
    ("Glycolic Acid",          "Glycolic Acid",                     4, "AHA Exfoliant",        "Strongest AHA; increases photosensitivity."),
    ("Mandelic Acid",          "Mandelic Acid",                     2, "AHA Exfoliant",        "Gentle AHA from bitter almonds; less irritating."),
    ("Tranexamic Acid",        "Tranexamic Acid",                   1, "Brightening",          "Powerful, gentle hyperpigmentation treatment."),
    ("Bakuchiol",              "Bakuchiol",                         1, "Retinol Alternative",  "Plant retinol; safe in pregnancy, no photosensitivity."),
    ("Witch Hazel",            "Hamamelis Virginiana Extract",      3, "Astringent",           "Tightens pores; can trigger rosacea or dryness."),
    ("Methylisothiazolinone",  "Methylisothiazolinone",             9, "Preservative",         "Potent allergen; banned in EU leave-on products."),
    ("Argan Oil",              "Argania Spinosa Kernel Oil",        1, "Emollient",            "Lightweight non-comedogenic oil; great for hair gloss."),
    ("Coconut Oil",            "Cocos Nucifera Oil",                2, "Emollient",            "Rich moisturizer; comedogenic for some skin types."),
    ("Castor Oil",             "Ricinus Communis Seed Oil",         1, "Emollient",            "Thick oil; can weigh down fine hair."),
    ("Biotin",                 "Biotin",                            1, "Vitamin B7",           "Supports keratin; promotes hair & nail health."),
    ("Keratin",                "Hydrolyzed Keratin",                1, "Hair Protein",         "Fills cuticle gaps; reduces frizz, adds strength."),
    ("Hydrolyzed Silk",        "Hydrolyzed Silk",                   1, "Conditioning Agent",   "Lightweight protein; adds softness and shine."),
    ("Zinc Pyrithione",        "Zinc Pyrithione",                   2, "Antifungal",           "Active ingredient in anti-dandruff shampoos."),
    ("Piroctone Olamine",      "Piroctone Olamine",                 1, "Antifungal",           "Gentler anti-dandruff alternative to zinc pyrithione."),
    ("Tea Tree Oil",           "Melaleuca Alternifolia Leaf Oil",   3, "Antimicrobial",        "Natural antiseptic; can irritate sensitive scalps."),
    ("Peppermint Oil",         "Mentha Piperita Oil",               4, "Cooling Agent",        "Stimulates scalp circulation; rosacea trigger."),
    ("Rosemary Extract",       "Rosmarinus Officinalis Extract",    1, "Antioxidant",          "DHT-blocking properties; supports hair density."),
    ("Cyclopentasiloxane",     "Cyclopentasiloxane",                4, "Silicone",             "Lightweight silicone; can build up on fine hair."),
    ("Propanediol",            "Propanediol",                       1, "Humectant",            "Plant-derived glycol; gentle and effective."),
    ("Butylene Glycol",        "Butylene Glycol",                   1, "Humectant/Solvent",    "Penetration enhancer and humectant."),
    ("Sodium PCA",             "Sodium PCA",                        1, "Humectant",            "Natural moisturizing factor component."),
    ("Urea",                   "Urea",                              1, "Keratolytic",          "Softens thickened skin; strong humectant."),
    ("Polyglutamic Acid",      "Polyglutamic Acid",                 1, "Humectant",            "Holds 5× more moisture than hyaluronic acid."),
    ("Kaolin",                 "Kaolin",                            1, "Absorbent",            "Gentle clay; absorbs oil without over-drying."),
    ("DMDM Hydantoin",         "DMDM Hydantoin",                    7, "Preservative",         "Formaldehyde-releasing preservative; allergy concern."),
    ("Propylene Glycol",       "Propylene Glycol",                  3, "Humectant/Solvent",    "Common carrier; potential sensitizer for eczema-prone."),
    ("Collagen Hydrolyzed",    "Hydrolyzed Collagen",               1, "Conditioning",         "Improves skin elasticity; film-forming."),
    ("Sea Kelp Extract",       "Macrocystis Pyrifera Extract",      1, "Soothing",             "Rich in minerals; calming for skin and scalp."),
    ("Apple Cider Vinegar",    "Pyrus Malus Fruit Vinegar",         2, "pH Balancer",          "Clarifies scalp buildup; balances hair pH."),
    ("Neem Oil",               "Azadirachta Indica Seed Oil",       2, "Antimicrobial",        "Antifungal scalp treatment; strong odor."),
    ("Saw Palmetto Extract",   "Serenoa Serrulata Fruit Extract",   1, "DHT Blocker",          "Inhibits 5-alpha-reductase; supports hair retention."),
]

PRODUCTS = [
    # (name, brand, category, subcategory, price, retailer, rating, review_count, image_url, ingredients_names)
    (
        "CeraVe Moisturizing Cream", "CeraVe", "skincare", "moisturizer", 19.99, "ulta", 4.8, 82000, None,
        ["Water","Glycerin","Cetearyl Alcohol","Ceramide NP","Dimethicone","Phenoxyethanol","Allantoin"]
    ),
    (
        "The Ordinary Niacinamide 10% + Zinc 1%", "The Ordinary", "skincare", "serum", 8.90, "sephora", 4.6, 41000, None,
        ["Water","Niacinamide","Glycerin","Zinc Oxide","Phenoxyethanol"]
    ),
    (
        "La Roche-Posay Toleriane Double Repair Face Moisturizer", "La Roche-Posay", "skincare", "moisturizer", 29.99, "ulta", 4.7, 18000, None,
        ["Water","Glycerin","Ceramide NP","Niacinamide","Panthenol","Allantoin","Phenoxyethanol"]
    ),
    (
        "Paula's Choice 2% BHA Liquid Exfoliant", "Paula's Choice", "skincare", "exfoliant", 36.00, "sephora", 4.7, 21000, None,
        ["Water","Salicylic Acid","Glycerin","Allantoin","Phenoxyethanol"]
    ),
    (
        "Neutrogena Hydro Boost Water Gel", "Neutrogena", "skincare", "moisturizer", 27.49, "ulta", 4.5, 33000, None,
        ["Water","Hyaluronic Acid","Glycerin","Dimethicone","Phenoxyethanol"]
    ),
    (
        "EltaMD UV Clear Broad-Spectrum SPF 46", "EltaMD", "suncare", "sunscreen", 41.00, "sephora", 4.8, 15000, None,
        ["Zinc Oxide","Water","Niacinamide","Glycerin","Hyaluronic Acid","Phenoxyethanol"]
    ),
    (
        "Supergoop! Unseen Sunscreen SPF 40", "Supergoop!", "suncare", "sunscreen", 42.00, "sephora", 4.7, 22000, None,
        ["Avobenzone","Oxybenzone","Water","Glycerin","Dimethicone","Vitamin E","Ferulic Acid"]
    ),
    (
        "Tatcha The Water Cream", "Tatcha", "skincare", "moisturizer", 72.00, "sephora", 4.6, 8900, None,
        ["Water","Glycerin","Aloe Vera","Green Tea Extract","Centella Asiatica","Allantoin","Phenoxyethanol"]
    ),
    (
        "Drunk Elephant T.L.C. Framboos Glycolic Night Serum", "Drunk Elephant", "skincare", "serum", 90.00, "sephora", 4.4, 5700, None,
        ["Water","Lactic Acid","Glycerin","Salicylic Acid","Vitamin C","Green Tea Extract","Phenoxyethanol"]
    ),
    (
        "Skinceuticals C E Ferulic", "SkinCeuticals", "skincare", "serum", 182.00, "sephora", 4.8, 12000, None,
        ["Water","Vitamin C","Vitamin E","Ferulic Acid","Glycerin","Phenoxyethanol"]
    ),
    (
        "Fenty Beauty Pro Filt'r Soft Matte Foundation", "Fenty Beauty", "makeup", "foundation", 40.00, "sephora", 4.5, 24000, None,
        ["Water","Dimethicone","Glycerin","Iron Oxides","Talc","Mica","Phenoxyethanol","Fragrance"]
    ),
    (
        "NARS Natural Radiant Longwear Foundation", "NARS", "makeup", "foundation", 54.00, "sephora", 4.4, 11000, None,
        ["Water","Dimethicone","Glycerin","Iron Oxides","Titanium Dioxide","Mica","Phenoxyethanol"]
    ),
    (
        "Tarte Shape Tape Concealer", "Tarte", "makeup", "concealer", 32.00, "ulta", 4.6, 30000, None,
        ["Water","Dimethicone","Iron Oxides","Shea Butter","Vitamin E","Phenoxyethanol","Fragrance"]
    ),
    (
        "Charlotte Tilbury Flawless Filter", "Charlotte Tilbury", "makeup", "primer", 49.00, "sephora", 4.5, 9000, None,
        ["Water","Dimethicone","Mica","Iron Oxides","Jojoba Oil","Phenoxyethanol","Fragrance"]
    ),
    (
        "Anastasia Beverly Hills Brow Wiz", "Anastasia Beverly Hills", "makeup", "brow", 25.00, "ulta", 4.7, 50000, None,
        ["Iron Oxides","Mica","Dimethicone","Cetearyl Alcohol","Phenoxyethanol"]
    ),
    (
        "Urban Decay All Nighter Setting Spray", "Urban Decay", "makeup", "setting spray", 36.00, "ulta", 4.5, 14000, None,
        ["Water","Alcohol Denat","Glycerin","Dimethicone","Phenoxyethanol"]
    ),
    (
        "Benefit Gimme Brow+ Volumizing Eyebrow Gel", "Benefit", "makeup", "brow", 28.00, "sephora", 4.6, 11000, None,
        ["Water","Alcohol Denat","Iron Oxides","Mica","Phenoxyethanol","Fragrance"]
    ),
    (
        "Too Faced Better Than Sex Mascara", "Too Faced", "makeup", "mascara", 27.00, "ulta", 4.5, 38000, None,
        ["Water","Iron Oxides","Cetearyl Alcohol","Glycerin","Phenoxyethanol","Fragrance"]
    ),
    (
        "Rare Beauty Soft Pinch Liquid Blush", "Rare Beauty", "makeup", "blush", 23.00, "sephora", 4.7, 17000, None,
        ["Water","Glycerin","Iron Oxides","Mica","Dimethicone","Phenoxyethanol"]
    ),
    (
        "e.l.f. Halo Glow Liquid Filter", "e.l.f. Cosmetics", "makeup", "primer", 14.00, "ulta", 4.6, 28000, None,
        ["Water","Glycerin","Mica","Dimethicone","Aloe Vera","Hyaluronic Acid","Phenoxyethanol"]
    ),
    (
        "Aveeno Daily Moisturizing Lotion", "Aveeno", "skincare", "body moisturizer", 11.98, "ulta", 4.7, 45000, None,
        ["Water","Glycerin","Colloidal Oatmeal","Dimethicone","Cetearyl Alcohol","Phenoxyethanol"]
    ),
    (
        "First Aid Beauty Ultra Repair Cream", "First Aid Beauty", "skincare", "moisturizer", 36.00, "ulta", 4.7, 9000, None,
        ["Water","Glycerin","Shea Butter","Colloidal Oatmeal","Ceramide NP","Allantoin","Phenoxyethanol"]
    ),
    (
        "Peter Thomas Roth Retinol Fusion PM Night Serum", "Peter Thomas Roth", "skincare", "serum", 65.00, "sephora", 4.3, 4200, None,
        ["Water","Retinol","Glycerin","Vitamin E","Peptides","Phenoxyethanol"]
    ),
    (
        "RoC Retinol Correxion Line Smoothing Serum", "RoC", "skincare", "serum", 26.99, "ulta", 4.4, 7500, None,
        ["Water","Retinol","Glycerin","Dimethicone","Vitamin E","Phenoxyethanol"]
    ),
    (
        "Sunday Riley Good Genes All-In-One Lactic Acid Treatment", "Sunday Riley", "skincare", "treatment", 85.00, "sephora", 4.5, 6800, None,
        ["Water","Lactic Acid","Glycerin","Aloe Vera","Licorice Root","Phenoxyethanol","Fragrance"]
    ),
    (
        "Kiehl's Ultra Facial Cream", "Kiehl's", "skincare", "moisturizer", 38.00, "sephora", 4.6, 9800, None,
        ["Water","Glycerin","Squalane","Jojoba Oil","Allantoin","Cetearyl Alcohol","Phenoxyethanol"]
    ),
    (
        "Youth To The People Superfood Air-Whip Moisture Cream", "Youth To The People", "skincare", "moisturizer", 58.00, "sephora", 4.4, 3500, None,
        ["Water","Glycerin","Green Tea Extract","Aloe Vera","Vitamin C","Centella Asiatica","Phenoxyethanol"]
    ),
    (
        "Innisfree Green Tea Seed Serum", "Innisfree", "skincare", "serum", 30.00, "sephora", 4.5, 5200, None,
        ["Water","Green Tea Extract","Glycerin","Hyaluronic Acid","Niacinamide","Allantoin","Phenoxyethanol"]
    ),
    (
        "COSRX Advanced Snail 96 Mucin Power Essence", "COSRX", "skincare", "essence", 25.00, "ulta", 4.7, 13000, None,
        ["Water","Glycerin","Hyaluronic Acid","Allantoin","Panthenol","Phenoxyethanol"]
    ),
    (
        "Glow Recipe Watermelon Glow Niacinamide Dew Drops", "Glow Recipe", "skincare", "serum", 42.00, "sephora", 4.5, 7300, None,
        ["Water","Niacinamide","Glycerin","Hyaluronic Acid","Vitamin C","Centella Asiatica","Phenoxyethanol"]
    ),
    # ── More Skincare ──
    (
        "Cetaphil Gentle Skin Cleanser", "Cetaphil", "skincare", "cleanser", 14.99, "ulta", 4.7, 55000, None,
        ["Water","Glycerin","Cetearyl Alcohol","Propylene Glycol","Panthenol","Phenoxyethanol"]
    ),
    (
        "CeraVe Foaming Facial Cleanser", "CeraVe", "skincare", "cleanser", 15.99, "ulta", 4.6, 38000, None,
        ["Water","Glycerin","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Ceramide NP","Niacinamide","Phenoxyethanol"]
    ),
    (
        "The Ordinary Glycolic Acid 7% Toning Solution", "The Ordinary", "skincare", "toner", 12.00, "sephora", 4.3, 19000, None,
        ["Water","Glycolic Acid","Glycerin","Aloe Vera","Phenoxyethanol"]
    ),
    (
        "Laneige Water Sleeping Mask", "Laneige", "skincare", "mask", 29.00, "sephora", 4.7, 16000, None,
        ["Water","Glycerin","Butylene Glycol","Sodium PCA","Hyaluronic Acid","Centella Asiatica","Phenoxyethanol"]
    ),
    (
        "Clinique Moisture Surge 100H Auto-Replenishing Hydrator", "Clinique", "skincare", "moisturizer", 52.00, "sephora", 4.6, 13000, None,
        ["Water","Glycerin","Hyaluronic Acid","Aloe Vera","Allantoin","Propylene Glycol","Phenoxyethanol"]
    ),
    (
        "The Inkey List Tranexamic Acid Hyperpigmentation Treatment", "The Inkey List", "skincare", "treatment", 14.99, "sephora", 4.4, 8200, None,
        ["Water","Tranexamic Acid","Glycerin","Niacinamide","Propanediol","Phenoxyethanol"]
    ),
    (
        "Drunk Elephant Protini Polypeptide Cream", "Drunk Elephant", "skincare", "moisturizer", 68.00, "sephora", 4.5, 9400, None,
        ["Water","Glycerin","Peptides","Collagen Hydrolyzed","Ceramide NP","Propanediol","Phenoxyethanol"]
    ),
    (
        "COSRX Propolis Light Ampule", "COSRX", "skincare", "serum", 22.00, "ulta", 4.6, 6500, None,
        ["Water","Propanediol","Glycerin","Hyaluronic Acid","Centella Asiatica","Phenoxyethanol"]
    ),
    (
        "Purito Daily Go-To Sunscreen SPF 50+", "Purito", "suncare", "sunscreen", 19.00, "amazon", 4.5, 9800, None,
        ["Water","Zinc Oxide","Glycerin","Propanediol","Butylene Glycol","Polyglutamic Acid","Phenoxyethanol"]
    ),
    (
        "Isntree Hyaluronic Acid Watery Sun Gel SPF 50+", "Isntree", "suncare", "sunscreen", 22.00, "amazon", 4.7, 7200, None,
        ["Water","Zinc Oxide","Hyaluronic Acid","Glycerin","Sodium PCA","Centella Asiatica","Phenoxyethanol"]
    ),
    (
        "Biore UV Aqua Rich Watery Essence SPF 50+", "Biore", "suncare", "sunscreen", 18.00, "amazon", 4.8, 24000, None,
        ["Water","Avobenzone","Glycerin","Hyaluronic Acid","Butylene Glycol","Dimethicone","Phenoxyethanol"]
    ),
    (
        "Sunday Riley C.E.O. Glow Vitamin C + Turmeric Face Oil", "Sunday Riley", "skincare", "face oil", 55.00, "sephora", 4.4, 4100, None,
        ["Squalane","Vitamin C","Jojoba Oil","Argan Oil","Vitamin E","Ferulic Acid","Fragrance"]
    ),
    (
        "Youth To The People Adaptogen Deep Moisture Cream", "Youth To The People", "skincare", "moisturizer", 62.00, "sephora", 4.4, 3100, None,
        ["Water","Glycerin","Squalane","Ceramide NP","Sea Kelp Extract","Centella Asiatica","Phenoxyethanol"]
    ),
    # ── More Makeup ──
    (
        "Milk Makeup Hydro Grip Primer", "Milk Makeup", "makeup", "primer", 38.00, "sephora", 4.5, 12000, None,
        ["Water","Glycerin","Hyaluronic Acid","Aloe Vera","Niacinamide","Propanediol","Phenoxyethanol"]
    ),
    (
        "Maybelline Fit Me Matte + Poreless Foundation", "Maybelline", "makeup", "foundation", 10.99, "ulta", 4.4, 67000, None,
        ["Water","Dimethicone","Glycerin","Talc","Iron Oxides","Titanium Dioxide","Phenoxyethanol"]
    ),
    (
        "Glossier Cloud Paint", "Glossier", "makeup", "blush", 22.00, "sephora", 4.6, 9500, None,
        ["Water","Glycerin","Dimethicone","Iron Oxides","Mica","Centella Asiatica","Phenoxyethanol"]
    ),
    (
        "NYX Professional Makeup Epic Ink Liner", "NYX", "makeup", "eyeliner", 12.00, "ulta", 4.5, 28000, None,
        ["Water","Iron Oxides","Acrylates Copolymer","Glycerin","Phenoxyethanol","Fragrance"]
    ),
    (
        "ColourPop Super Shock Cheek", "ColourPop", "makeup", "blush", 9.00, "ulta", 4.6, 21000, None,
        ["Dimethicone","Mica","Iron Oxides","Glycerin","Jojoba Oil","Vitamin E","Phenoxyethanol"]
    ),
    # ── Haircare ──
    (
        "Head & Shoulders Classic Clean Shampoo", "Head & Shoulders", "haircare", "shampoo", 9.99, "ulta", 4.5, 42000, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Zinc Pyrithione","Glycerin","Fragrance","Methylisothiazolinone"]
    ),
    (
        "Pantene Pro-V Repair & Protect Shampoo", "Pantene", "haircare", "shampoo", 7.99, "ulta", 4.4, 38000, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Dimethicone","Glycerin","Panthenol","Fragrance"]
    ),
    (
        "Briogeo Scalp Revival Charcoal + Tea Tree Shampoo", "Briogeo", "haircare", "shampoo", 42.00, "sephora", 4.6, 7800, None,
        ["Water","Cocamidopropyl Betaine","Glycerin","Tea Tree Oil","Peppermint Oil","Zinc Pyrithione","Phenoxyethanol"]
    ),
    (
        "OGX Coconut Milk Moisturizing Shampoo", "OGX", "haircare", "shampoo", 9.49, "ulta", 4.3, 22000, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Coconut Oil","Glycerin","Panthenol","Fragrance"]
    ),
    (
        "Pureology Hydrate Shampoo", "Pureology", "haircare", "shampoo", 34.00, "ulta", 4.7, 11000, None,
        ["Water","Cocamidopropyl Betaine","Glycerin","Panthenol","Argan Oil","Keratin","Phenoxyethanol"]
    ),
    (
        "Olaplex No. 4 Bond Maintenance Shampoo", "Olaplex", "haircare", "shampoo", 30.00, "sephora", 4.6, 15000, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Butylene Glycol","Keratin","Hydrolyzed Silk","Phenoxyethanol"]
    ),
    (
        "Nizoral A-D Anti-Dandruff Shampoo", "Nizoral", "haircare", "shampoo", 15.99, "ulta", 4.6, 19000, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Glycerin","Propylene Glycol","Fragrance","DMDM Hydantoin"]
    ),
    (
        "WOW Apple Cider Vinegar Shampoo", "WOW Skin Science", "haircare", "shampoo", 19.95, "amazon", 4.4, 14000, None,
        ["Water","Cocamidopropyl Betaine","Apple Cider Vinegar","Glycerin","Argan Oil","Rosemary Extract","Phenoxyethanol"]
    ),
    (
        "Aveda Invati Advanced Exfoliating Shampoo", "Aveda", "haircare", "shampoo", 44.00, "sephora", 4.5, 8900, None,
        ["Water","Sodium Laureth Sulfate","Glycerin","Salicylic Acid","Saw Palmetto Extract","Rosemary Extract","Phenoxyethanol"]
    ),
    (
        "Kristin Ess Signature Shampoo", "Kristin Ess", "haircare", "shampoo", 15.00, "ulta", 4.5, 9200, None,
        ["Water","Cocamidopropyl Betaine","Glycerin","Panthenol","Biotin","Propanediol","Phenoxyethanol"]
    ),
    (
        "Olaplex No. 5 Bond Maintenance Conditioner", "Olaplex", "haircare", "conditioner", 30.00, "sephora", 4.6, 12000, None,
        ["Water","Cetearyl Alcohol","Glycerin","Keratin","Hydrolyzed Silk","Butylene Glycol","Phenoxyethanol"]
    ),
    (
        "SheaMoisture Coconut & Hibiscus Curl & Shine Conditioner", "SheaMoisture", "haircare", "conditioner", 13.99, "ulta", 4.5, 16000, None,
        ["Water","Cetearyl Alcohol","Coconut Oil","Shea Butter","Glycerin","Panthenol","Fragrance"]
    ),
    (
        "Cantu Shea Butter Leave-In Conditioning Repair Cream", "Cantu", "haircare", "leave-in", 9.99, "ulta", 4.6, 28000, None,
        ["Water","Shea Butter","Cetearyl Alcohol","Coconut Oil","Castor Oil","Glycerin","Fragrance"]
    ),
    (
        "Moroccanoil Treatment", "Moroccanoil", "haircare", "hair oil", 46.00, "sephora", 4.8, 21000, None,
        ["Cyclopentasiloxane","Dimethicone","Argan Oil","Vitamin E","Fragrance","Phenoxyethanol"]
    ),
    (
        "It's a 10 Miracle Leave-In Product", "It's a 10", "haircare", "leave-in", 21.00, "ulta", 4.6, 18000, None,
        ["Water","Cetearyl Alcohol","Dimethicone","Cyclopentasiloxane","Panthenol","Silk","Fragrance"]
    ),
    (
        "Briogeo Don't Despair Repair Deep Conditioning Mask", "Briogeo", "haircare", "mask", 42.00, "sephora", 4.7, 9300, None,
        ["Water","Cetearyl Alcohol","Argan Oil","Rosehip Oil","Keratin","Biotin","Phenoxyethanol"]
    ),
    (
        "Olaplex No. 3 Hair Perfector", "Olaplex", "haircare", "treatment", 30.00, "sephora", 4.7, 25000, None,
        ["Water","Propanediol","Bis-Aminopropyl Diglycol Dimaleate","Cetearyl Alcohol","Keratin","Phenoxyethanol"]
    ),
    (
        "The Ordinary Multi-Peptide Serum For Hair Density", "The Ordinary", "haircare", "serum", 17.90, "sephora", 4.4, 11000, None,
        ["Water","Propanediol","Glycerin","Peptides","Caffeine","Saw Palmetto Extract","Rosemary Extract","Phenoxyethanol"]
    ),
    (
        "Vegamour GRO Hair Serum", "Vegamour", "haircare", "serum", 52.00, "sephora", 4.3, 7200, None,
        ["Water","Propanediol","Glycerin","Saw Palmetto Extract","Caffeine","Biotin","Rosemary Extract","Phenoxyethanol"]
    ),
    (
        "Christophe Robin Cleansing Purifying Scalp Scrub", "Christophe Robin", "haircare", "scalp treatment", 55.00, "sephora", 4.5, 5600, None,
        ["Water","Sea Salt","Glycerin","Kaolin","Sea Kelp Extract","Propanediol","Phenoxyethanol"]
    ),
    (
        "Redken All Soft Conditioner", "Redken", "haircare", "conditioner", 28.00, "ulta", 4.6, 13000, None,
        ["Water","Cetearyl Alcohol","Dimethicone","Argan Oil","Glycerin","Panthenol","Fragrance"]
    ),
    (
        "Arvazallia Premium Argan Oil Hair Mask", "Arvazallia", "haircare", "mask", 16.95, "amazon", 4.5, 21000, None,
        ["Water","Cetearyl Alcohol","Argan Oil","Coconut Oil","Keratin","Glycerin","Phenoxyethanol"]
    ),
    (
        "Nioxin System 2 Shampoo", "Nioxin", "haircare", "shampoo", 26.00, "ulta", 4.4, 8700, None,
        ["Water","Sodium Laureth Sulfate","Cocamidopropyl Betaine","Glycerin","Neem Oil","Saw Palmetto Extract","Phenoxyethanol"]
    ),
    (
        "dpHUE ACV Hair Rinse", "dpHUE", "haircare", "treatment", 35.00, "sephora", 4.5, 6100, None,
        ["Water","Apple Cider Vinegar","Glycerin","Aloe Vera","Argan Oil","Propanediol","Phenoxyethanol"]
    ),
    (
        "Kérastase Nutritive Masquintense Thick Hair Mask", "Kérastase", "haircare", "mask", 65.00, "sephora", 4.7, 4800, None,
        ["Water","Cetearyl Alcohol","Dimethicone","Shea Butter","Argan Oil","Keratin","Fragrance"]
    ),
]


def seed():
    conn = get_db()
    c    = conn.cursor()

    # Insert ingredients
    ing_id_map = {}
    for row in INGREDIENTS:
        name, inci, score, func, desc = row
        existing = c.execute("SELECT id FROM ingredients WHERE name=?", (name,)).fetchone()
        if existing:
            ing_id_map[name] = existing['id']
        else:
            c.execute("""
                INSERT INTO ingredients (name, inci_name, ewg_score, function, description)
                VALUES (?, ?, ?, ?, ?)
            """, (name, inci, score, func, desc))
            ing_id_map[name] = c.lastrowid

    conn.commit()
    print(f"[Seed] Inserted {len(ing_id_map)} ingredients.")

    # Insert products + links
    prod_count = 0
    for row in PRODUCTS:
        name, brand, cat, subcat, price, retailer, rating, reviews, img_url, ing_names = row
        existing = c.execute("SELECT id FROM products WHERE name=? AND brand=?", (name, brand)).fetchone()
        if existing:
            pid = existing['id']
        else:
            c.execute("""
                INSERT INTO products (name, brand, category, subcategory, price, retailer, rating, review_count, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, brand, cat, subcat, price, retailer, rating, reviews, img_url))
            pid = c.lastrowid
            prod_count += 1

        # Link ingredients
        for pos, ing_name in enumerate(ing_names, start=1):
            iid = ing_id_map.get(ing_name)
            if iid:
                c.execute("""
                    INSERT OR IGNORE INTO product_ingredients (product_id, ingredient_id, position)
                    VALUES (?, ?, ?)
                """, (pid, iid, pos))

    conn.commit()
    conn.close()
    print(f"[Seed] Inserted {prod_count} new products.")
    print("[Seed] Done! Run: python app.py")


if __name__ == '__main__':
    seed()
