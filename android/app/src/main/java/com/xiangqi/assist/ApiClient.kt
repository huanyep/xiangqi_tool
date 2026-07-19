package com.xiangqi.assist

import android.graphics.Bitmap
import kotlinx.coroutines.Dispatchers
import java.io.Serializable
import kotlinx.coroutines.withContext
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.concurrent.TimeUnit

/**
 * PC 服务端通信客户端
 * 发送截图 → 接收走法建议
 */
class ApiClient(private val baseUrl: String) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build()

    data class AnalysisResult(
        val bestMove: String,
        val score: String,
        val scoreColor: String,
        val depth: String,
        val pv: String,
        val fen: String
    ) : Serializable

    /**
     * 上传截图并获取分析结果
     */
    suspend fun analyze(bitmap: Bitmap): AnalysisResult? = withContext(Dispatchers.IO) {
        try {
            // Bitmap → JPEG bytes (压缩到 85%)
            val stream = ByteArrayOutputStream()
            bitmap.compress(Bitmap.CompressFormat.JPEG, 85, stream)
            val imageBytes = stream.toByteArray()

            // Multipart POST
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("file", "screenshot.jpg",
                    imageBytes.toRequestBody("image/jpeg".toMediaType()))
                .build()

            val request = Request.Builder()
                .url("$baseUrl/analyze")
                .post(requestBody)
                .build()

            val response = client.newCall(request).execute()
            val body = response.body?.string() ?: return@withContext null

            val json = JSONObject(body)
            if (json.has("error")) return@withContext null

            AnalysisResult(
                bestMove = json.optString("best_move", "--"),
                score = json.optString("score_display", "0.0"),
                scoreColor = json.optString("score_color", ""),
                depth = json.optString("depth", "0"),
                pv = json.optString("pv", ""),
                fen = json.optString("fen", "")
            )
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    /**
     * 测试连接
     */
    suspend fun testConnection(): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url(baseUrl)
                .head()
                .build()
            val response = client.newCall(request).execute()
            response.isSuccessful
        } catch (e: Exception) {
            false
        }
    }
}
