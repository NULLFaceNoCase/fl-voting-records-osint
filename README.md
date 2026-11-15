# OSINT Scripts to parse public Florida voting records data

Scripts used to parse through Florida's public voting records data that can be obtained for free.

[Voter Extract Request](https://dos.fl.gov/elections/data-statistics/voter-registration-statistics/voter-extract-request/)

[Exception Form](https://files.floridados.gov/media/709592/address-confidentiality-exemption-form-07-2025.pdf)

*Uses the Voter Extract File Layout from May 2026. See "FINAL_Voter_Extract_Disk_File_Layout_rev_20260504.pdf"*


## Disclaimer
This software is provided for educational purposes and to help Floridians understand their digital footprint. By downloading, using, modifying, or distributing this software, you acknowledge and agree that:

- You are solely responsible for how you use this software and any information obtained through it.

- This software is intended to access and compile publicly available information and is not designed for malicious, unlawful, or unauthorized activities.

- Respect for individual privacy is expected. This software must not be used to dox, harass, stalk, intimidate, threaten, or otherwise target any individual.

- You are responsible for ensuring that your use of this software complies with applicable laws and regulations.

- The author does not endorse or encourage the misuse of this software or the information it collects.

- The author assumes no responsibility or liability for any damages, losses, legal consequences, or other issues arising from the use or misuse of this software.*

This software is provided "AS IS", without warranties or guarantees of any kind. By using this software, you accept full responsibility for your actions and any consequences resulting from its use.

## Example Voter Search (voterq.py):

*Need to pass in path containing voter data text files. Can pass the entire directory to search all counties or a specific file to search one county.*

Search for white voters in their 40s with the last name containing "doe" that are last registered in Tampa.
```
python voterq.py 20261109_Detail/ --last doe --city tampa --race white --age 40s --fields all --ndjson > test.json
```

Search for white voters in their 40s with the last name containing "doe" that are last registered in Hillsborough County.
```
python voterq.py 20261109_Detail/HIL_20261109.txt --last doe --race white --age 40s --fields all --ndjson > test.json
```

Search for republician native women voters
```
python voterq.py 20261109_Detail/ --gender female --party REP --race native --fields all --ndjson > test.json
```

Return the number of results for democratic party registered in a specific zip code.
```
python voterq.py 20261109_Detail/ --party DEM --zip 33772 --count
```

Search for all voters with a specified email address ending in "duck.com"
```
python voterq.py 20261109_Detail/ --where email='@duck.com' --fields all --ndjson > privacy_emails.json
```

Search for all voters with a specified email address ending in "proton.me"
```
python voterq.py 20261109_Detail/ --where email='@proton.me' --fields all --ndjson > privacy_emails.json
```

Return the number of voters with a public records exemption
```
python voterq.py 20261109_Detail/ --where public_records_exemption='Y' --fields all --count
```

## Example JSON Result Commands

Print all json results
```
jq . test.json
```

Print number of results from json file
```
jq -s length test.json
```

Further filter the json output - show only results with first name containing "john"
```
jq 'select((.name_first // "") | test("john"; "i"))' test.json
```

Filter output for results with an email specified
```
jq 'select(.email != null)' test.json
```

## Example Voter History Query (votehist.py)

*Voter ID can be obtained from voterq.py query.*

Searching all counties for all voter history of voter with id = 123456789
```
python votehist.py 20261109_VH03/ 123456789
```