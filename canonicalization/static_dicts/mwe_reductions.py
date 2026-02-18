"""
Multi-word expression (MWE) reductions for preprocessing.

GENERAL_MWE: Applies to any attribute. Maps verbose expressions to canonical short forms.
ATTRIBUTE_MWE: Attribute-specific overrides. Keyed by attribute_key, each maps expressions
               to canonical forms within that attribute's domain.

Applied AFTER abbreviation expansion, BEFORE lemmatization.
"""

GENERAL_MWE = {
    # Condition - aligned with condition_ontology.json hierarchy
    # new: brand new items in original packaging
    "brand new": "new",
    "brand-new": "new",
    "factory sealed": "new",
    "factory new": "new",
    "box packed": "new",
    "box piece": "new",
    "sealed pack": "new",
    "unopened": "new",
    "unused": "new",
    # like_new: virtually new with minimal imperfections (child of used)
    "like new": "like_new",
    "as good as new": "like_new",
    "mint condition": "like_new",
    "barely used": "like_new",
    "barely touched": "like_new",
    "hardly used": "like_new",
    # very_good: lightly used with minor cosmetic issues (child of used)
    "lightly used": "very_good",
    "gently used": "very_good",
    "gently worn": "very_good",
    "slightly used": "very_good",
    "excellent condition": "very_good",
    # good: shows wear from consistent use (child of used)
    "well used": "good",
    "good condition": "good",
    "well maintained": "good",
    # acceptable: heavy wear but usable (child of used)
    "heavily used": "acceptable",
    "fair condition": "acceptable",
    # used: generic used without specific sub-category
    "pre-owned": "used",
    "pre owned": "used",
    "preowned": "used",
    "second hand": "used",
    "second-hand": "used",
    "secondhand": "used",
    "2nd hand": "used",
    "previously owned": "used",
    "one owner": "used",
    "single owner": "used",
    # damaged: non-functional or needs repair
    "needs repair": "damaged",
    "needs fixing": "damaged",
    "for parts": "for_parts",
    "not working": "damaged",
    "not functional": "damaged",
    "dead": "damaged",

    # Availability / Timing
    "right away": "immediate",
    "right now": "immediate",
    "as soon as possible": "immediate",
    "asap": "immediate",
    "at the earliest": "immediate",
    "at your earliest convenience": "immediate",
    "on the spot": "immediate",
    "walk in": "immediate",
    "walk-in": "immediate",

    # Pricing
    "free of cost": "free",
    "no charge": "free",
    "no cost": "free",
    "complimentary": "free",
    "on the house": "free",
    "at no extra cost": "free",
    "negotiable price": "negotiable",
    "price negotiable": "negotiable",
    "best offer": "negotiable",
    "or best offer": "negotiable",
    "obo": "negotiable",
    "fixed price": "fixed",
    "firm price": "fixed",
    "no bargaining": "fixed",

    # Experience
    "entry level": "beginner",
    "entry-level": "beginner",
    "no experience": "beginner",
    "fresher": "beginner",
    "fresh graduate": "beginner",
    "mid level": "intermediate",
    "mid-level": "intermediate",
    "some experience": "intermediate",
    "senior level": "expert",
    "senior-level": "expert",
    "highly experienced": "expert",
    "very experienced": "expert",

    # Boolean-ish
    "not required": "no",
    "not needed": "no",
    "not necessary": "no",
    "optional": "no",
    "required": "yes",
    "mandatory": "yes",
    "must have": "yes",
    "must-have": "yes",
    "compulsory": "yes",
}

ATTRIBUTE_MWE = {
    "condition": {
        # new: brand new items
        "brand new": "new",
        "brand-new": "new",
        # like_new: virtually new (child of used)
        "like new": "like_new",
        "mint condition": "like_new",
        "barely used": "like_new",
        "barely touched": "like_new",
        "hardly used": "like_new",
        # very_good: lightly used (child of used)
        "lightly used": "very_good",
        "gently used": "very_good",
        "gently worn": "very_good",
        "excellent condition": "very_good",
        # good: shows consistent wear (child of used)
        "good condition": "good",
        # acceptable: heavy wear but usable (child of used)
        "fair condition": "acceptable",
        # used: generic
        "pre-owned": "used",
        "pre owned": "used",
        "second hand": "used",
        "second-hand": "used",
        "secondhand": "used",
        "2nd hand": "used",
        # refurbished
        "refurbished": "refurbished",
        "renewed": "refurbished",
        "reconditioned": "refurbished",
        "restored": "refurbished",
        # for_parts
        "for parts": "for_parts",
        "for spares": "for_parts",
        "parts only": "for_parts",
        "salvage title": "for_parts",
    },
    "fuel": {
        "petrol": "gasoline",
        "gas": "gasoline",
        "diesel fuel": "diesel",
        "electric motor": "electric",
        "battery powered": "electric",
        "battery-powered": "electric",
        "plug in hybrid": "plug in hybrid electric",
        "plug-in hybrid": "plug in hybrid electric",
        "compressed natural gas": "cng",
        "liquefied petroleum gas": "lpg",
        "flex fuel": "flex fuel",
        "bi fuel": "bi fuel",
        "dual fuel": "bi fuel",
        "hydrogen fuel cell": "hydrogen",
    },
    "transmission": {
        "manual transmission": "manual",
        "stick shift": "manual",
        "standard": "manual",
        "automatic transmission": "automatic",
        "auto": "automatic",
        "semi automatic": "semi automatic",
        "semi-automatic": "semi automatic",
        "tiptronic": "automatic",
        "paddle shift": "automatic",
    },
    "furnishing": {
        "fully furnished": "furnished",
        "fully-furnished": "furnished",
        "semi furnished": "semi furnished",
        "semi-furnished": "semi furnished",
        "partially furnished": "semi furnished",
        "not furnished": "unfurnished",
        "bare shell": "unfurnished",
    },
    "employment_type": {
        "full time": "full time",
        "full-time": "full time",
        "part time": "part time",
        "part-time": "part time",
        "work from home": "remote",
        "wfh": "remote",
        "on site": "onsite",
        "on-site": "onsite",
        "in office": "onsite",
        "in-office": "onsite",
    },
    "diet": {
        "pure veg": "vegetarian",
        "pure vegetarian": "vegetarian",
        "strict vegetarian": "vegetarian",
        "non veg": "non vegetarian",
        "non-veg": "non vegetarian",
        "nonveg": "non vegetarian",
        "egg": "eggetarian",
        "eggitarian": "eggetarian",
    },
}
