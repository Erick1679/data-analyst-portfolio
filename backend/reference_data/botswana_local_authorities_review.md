# Botswana local authorities — reference review (not an import)

Botswana's Ministry of Local Government and Traditional Affairs currently
describes **31 local authorities**. A council is a governing institution, not
automatically an additional geographic place. Do **not** load this list with
`import_places_csv` or create 31 `GeographicPlace` children without a
reviewed boundary-to-council crosswalk.

## Primary references

- [Ministry of Local Government and Traditional Affairs](https://gov.bw/ministries/ministry-local-government-and-traditional-affairs) — ministry overview and 31-council list.
- [Government local authorities directory](https://www.gov.bw/local-authorities-view) — names and contact directory; may disagree on some titles.

## Ministry's 31 listed councils (source wording, unnormalised)

1. Bobirwa District Council
2. Boteti District Council
3. Charleshill District Council
4. Chobe District Council
5. Francistown Town Council
6. Gaborone City Council
7. Ghanzi District Council
8. Goodhope District Council
9. Hukuntsi District Council
10. Jwaneng District Council
11. Kanye District Council
12. Kgatleng District Council
13. Kweneng District Council
14. Letlhakeng District Council
15. Lobatse Town Council
16. Mabutsane District Council
17. Mahalapye District Council
18. Mogoditshane-Thamaga District Council
19. Moshupa District Council
20. North East District Council
21. North West District Council
22. Okavango District Council
23. Palapye District Council
24. Ramotswa District Council
25. Selibe Phikwe Town Council
26. Serowe District Council
27. SOWA Town Council
28. Tlokweng District Council
29. Tonota District Council
30. Tsabong District Council
31. Tutume District Council

## Outstanding quality checks

- The government directory refers to **Francistown City Council**, while the
  ministry's overview lists **Francistown Town Council**. Confirm the legal
  designation and use one verified canonical label with any alternate name
  stored as an alias.
- The directory refers to **Jwaneng Town Council**, while the overview lists
  **Jwaneng District Council**. Verify before assigning a council type.
- The 31 authorities are **not** equivalent to the 10 ISO districts, 2 cities
  and 5 towns currently stored for Botswana; some districts contain multiple
  councils, and urban and special jurisdictions may differ.
- **Orapa** is currently a town reference record, not evidence that an
  independent Orapa local authority appears among these 31 councils.
- Any further model should represent an independent `LocalAuthority` with
  source provenance, administrative type, and an **optional verified**
  relationship to the geographic area(s) it serves. Avoid guessing
  jurisdiction boundaries or enabling publication without permissions review.
