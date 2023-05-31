# KnowBe4 Scripts

Collection of scripts for scraping KnowBe4

## Logging in

All scraping scripts require a login cookie to KnowBe4. Login credentials must be stored
in a file called `auth/knowbe4.json`. The file should be structured as follows
(following the [knowbe4.template.json](knowbe4.template.json)):

```json
{
    "resource_type": "partner_admin",
    "email": "",
    "password": ""
}
```

This will then be used to log in to KnowBe4, thus creating the required session cookie.
