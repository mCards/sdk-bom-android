# mCards Android SDK Bill of Materials

The customer BoM **1.0.19** mirrors the tested dependency set in internal BoM
**1.0.19.26**. This release must be published before customers select the new version.

| SDK | Version |
| --- | --- |
| Core | 1.3.9.8 |
| Cards | 1.2.0 |
| Auth | 1.2.8.6 |
| Accounts | 1.3.4.6 |
| History | 1.2.1.3 |
| Features Marketplace | 1.1.6.2 |

The release also includes Cards SDK's `play-services-tapandpay:18.3.3` dependency.

## Customer installation

Configure the customer repository in `settings.gradle.kts`:

```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven {
            url = uri("https://maven.pkg.github.com/mCards/sdk-bom-android")
            credentials {
                username = providers.gradleProperty("GITHUB_USERNAME").get()
                password = providers.gradleProperty("GITHUB_TOKEN").get()
            }
        }
    }
}
```

Keep credentials in your user Gradle properties, outside source control. Use a GitHub token
with package-read access. Customers do not need access to Wantsa repositories.

```kotlin
implementation(platform("com.mcards.sdk:bom:1.0.19"))
implementation("com.mcards.sdk:cards")
implementation("com.mcards.sdk:auth") // Optional: mCards/Auth0 token provider
```

Always use the BoM: its strict constraints select a consistent CoreSDK version across SDKs.
The refreshed Cards demo uses Android 11/API 30 minimum, compile SDK 37, AGP 9.2.0 and
Gradle 9.5.0 and Kotlin 2.4.10. See the [Cards demo](https://github.com/mCards/sdk-cards-android-demo).

## Maintainer release procedure

`release.json` pins the reference packages. `release-lock.json` records SHA-256 hashes for
all staged artifacts. SDK AARs, POMs, Gradle module metadata and documentation jars are copied
unchanged; only the BoM's own coordinate changes from `bom-internal:1.0.19.26` to `bom:1.0.19`.
No SDK source code or credentials are copied into this repository.

1. Review and merge the release PR.
2. Configure the `customer-sdk-release` GitHub environment with the `GH_PACKAGES_USER`
   variable and `GH_PACKAGES_READ_TOKEN` / `GH_PACKAGES_WRITE_TOKEN` secrets. The read token
   needs access to the pinned Wantsa packages; the write token needs package-read/write
   access to `mCards/sdk-bom-android`. Both belong to the configured GitHub user.
3. Run **Customer SDK release** with `publish` unchecked to stage and verify the release.
4. Run it again with `publish` checked. Every artifact is staged and verified before any
   upload. Existing matching releases are skipped, differing or partial releases stop the
   process, and the BoM is published last. Maven handles checksums and version metadata.
5. Resolve and build the Cards demo using only Google, Maven Central and the customer
   repository before announcing availability.

No publication occurs on a pull request, merge, or default workflow run. Publication is an
explicit workflow action. Do not tell customers 1.0.19 is available until step 5 passes.
If an upload is interrupted, investigate any partial version before retrying; this tool
intentionally does not overwrite an immutable release.

Local preparation (Python 3.9+; JDK 17+ and Maven needed only for publishing):

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/release.py
```

Set `GH_PACKAGES_USER` and `GH_PACKAGES_READ_TOKEN` in the environment. For a future version,
update `release.json`, explicitly run `--write-lock`, review the resulting hashes, and commit
both files. `--write-lock` cannot be combined with `--publish`.

[SDK documentation](https://mcards.readme.io/docs/mcards-sdk-overview)
