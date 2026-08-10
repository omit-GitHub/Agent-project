plugins {
    id("com.android.application")
}

android {
    namespace = "com.huawei.aifttr.digitalpersonshell"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.huawei.aifttr.digitalpersonshell"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"

        // 仅 armeabi-v7a（与源库一致，BR-010）
        ndk { abiFilters += "armeabi-v7a" }
    }

    sourceSets {
        getByName("main") {
            jniLibs.srcDirs("src/main/jniLibs")
            assets.srcDirs("src/main/assets")
        }
    }

    signingConfigs {
        create("release") {
            storeFile = file("keystore/aispeechbox_1.jks")
            storePassword = "aispeechbox"
            keyAlias = "aispeechbox"
            keyPassword = "aispeechbox"
            enableV1Signing = true
            enableV2Signing = true
        }
        getByName("debug") {
            storeFile = file("keystore/aispeechbox_1.jks")
            storePassword = "aispeechbox"
            keyAlias = "aispeechbox"
            keyPassword = "aispeechbox"
            enableV1Signing = true
            enableV2Signing = true
        }
    }

    buildTypes {
        getByName("debug") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
        getByName("release") {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("release")
        }
    }

    buildFeatures {
        aidl = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    testOptions {
        unitTests {
            isReturnDefaultValues = true
        }
    }
}

// 语音能力（唤醒/ASR/TTS）接入：原 :voice SDK 适配层已并入 :app（com.guiagent.voice.*）；
// AndroidX + okhttp(云端 ASR/TTS/授权)；DUI lite SDK jar（fileTree，本地化）；
// native/模型资源（.so/.bin）已落地 app/src/main/{jniLibs,assets}。
dependencies {
    implementation(fileTree(mapOf("dir" to "src/libs", "include" to listOf("*.jar"))))
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:okhttp-sse:4.12.0")
    // JSON 序列化/解析（WebSocket 对话）：org.json 在 Android 单测 stub 下返回 null，故用 gson
    implementation("com.google.code.gson:gson:2.10.1")

    // 单元测试（TDD，JVM 跑，纯逻辑，Mock 隔离 SDK）
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.mockito:mockito-core:4.11.0")
}
