# Android SDKs Bill of Materials
The android SDKs are provided as a Bill of Materials (BoM). The BoM is a single dependency that acts as a bundle of the individual SDKs. Only the BoM version needs to be specified explicitly, and then the individual dependencies are handled automatically by the build system.

# Importing the Android BoM
A single BoM platform dependency must be declared, then individual SDKs are imported by declaring them individually without specifying versions. Only SDK dependencies explicitly declared will be imported. To import all five SDKs, add the following to your module-level build.gradle:

Groovy:
```
implementation(platform("com.mcards.sdk:bom:$latestVersion"))
implementation "com.mcards.sdk:cards"
implementation "com.mcards.sdk:auth"
implementation "com.mcards.sdk:accounts"
implementation "com.mcards.sdk:history"
implementation "com.mcards.sdk:fm"
```

Kotlin:
```
implementation(platform("com.mcards.sdk:bom:$latestVersion"))
implementation("com.mcards.sdk:cards")
implementation("com.mcards.sdk:auth")
implementation("com.mcards.sdk:accounts")
implementation("com.mcards.sdk:history")
implementation("com.mcards.sdk:fm")
```

If you only want to use certain SDKs, then simply omit the lines declaring implementations of the SDKs you don't want to import. The following example only imports the Cards and Auth SDKS.

Kotlin:
```
implementation(platform("com.mcards.sdk:bom:$latestVersion"))
implementation("com.mcards.sdk:cards")
implementation("com.mcards.sdk:auth")
```

And the following to the project settings.gradle (groovy):
```
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()

        maven {
            url = uri("https://maven.pkg.github.com/mymcard/sdk-bom-android")
            credentials {
                username = GITHUB_USERNAME
                password = GITHUB_TOKEN
            }
        }
    }
}
```

Where GITHUB_TOKEN is a github personal access token that you generate. See https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

# Documentation
[Documentation site](https://mcards.readme.io/)

[SDKs conceptual documentation](https://mcards.readme.io/docs/mcards-sdk-overview)

Password: mCardsDevDocs
