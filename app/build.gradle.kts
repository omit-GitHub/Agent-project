plugins {
    id("com.android.application")
}

android {
    namespace = "com.guiagent.executor"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.guiagent.executor"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        getByName("debug") {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_1_8
        targetCompatibility = JavaVersion.VERSION_1_8
    }
}

// 纯 Java,无 AndroidX、无 UI、无 native 库 -> universal APK,32 位 armeabi-v7a 可装
dependencies { }
