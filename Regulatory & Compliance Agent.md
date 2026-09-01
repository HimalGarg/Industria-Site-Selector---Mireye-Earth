### Regulatory & Compliance Agent

We’re building a **Regulatory & Compliance Due-Diligence Agent** that works alongside our existing **Crexi + Mireye property-analysis pipeline**.

For every industrial property listed on Crexi, we take its **address, coordinates, property type and listing information**, resolve the exact location and jurisdiction, and then collect publicly available records from **official US government sources**.

The agent checks:

* **EPA ECHO** → environmental permits, inspections, violations, enforcement, penalties and hazardous-waste/air/water compliance.
* **City/County/State government portals** → building permits, construction/renovation permits, inspections and violations.
* **Certificate of Occupancy records** → approved building use and occupancy classification.
* **Fire department/government records** → fire inspections, violations, permits and safety records where publicly available.
* **Official zoning/GIS databases** → zoning classification, permitted/conditional uses and land-use restrictions.

Because every US jurisdiction has different databases, a **Jurisdiction Resolver** identifies which official APIs, open-data portals or GIS systems are available for that property. If a source doesn't exist or isn't publicly accessible, we mark it **DATA_UNAVAILABLE** rather than assuming the property is compliant.

We then **normalize and cross-check all the records**. For example:

**Crexi:** Manufacturing Facility
**Zoning:** Light Industrial
**Occupancy:** Warehouse
**EPA:** Open environmental violation

→ The system flags this as a **potential regulatory risk** rather than blindly declaring it illegal.

EPA facilities are also matched using **GPS distance + address/name validation**, so a nearby facility isn't incorrectly attributed to our property.

After collecting the evidence, a **deterministic rule engine** calculates separate risk scores for:

**Environmental + Zoning + Building + Occupancy + Fire**

and combines them into an overall **Regulatory Risk Score**. We also calculate **data confidence/completeness**, because missing government data should never be treated as a clean record.

Finally, the LLM **does not decide whether the property is legally compliant**. It only explains the structured findings and evidence produced by the system. Every finding must be tied to an actual source record.

### Final output

**Regulatory Risk: MEDIUM — 61/100**
**Confidence: 82%**

* Environmental → Potential Risk
* Zoning → Clear
* Building → Clear
* Occupancy → Potential Risk
* Fire → Data Unavailable

with the **exact government evidence, source, record/date and reason for each flag**.

So the overall system becomes:

**Crexi → Mireye (property attractiveness) + Compliance Agent (government/regulatory risk) → Combined investment decision.**

The entire MVP is designed **free-first**, using EPA ECHO, Census services, FEMA and publicly available city/county/state government APIs, open-data portals and GIS systems.
