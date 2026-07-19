package com.xiangqi.assist

import android.app.*
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.*

/**
 * 截屏服务 — 使用 MediaProjection API 定时截屏
 */
class ScreenCaptureService : Service() {

    private lateinit var mediaProjection: android.media.projection.MediaProjection
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var captureJob: Job? = null

    private val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    companion object {
        const val EXTRA_RESULT_CODE = "result_code"
        const val EXTRA_RESULT_DATA = "result_data"
        const val EXTRA_SERVER_URL = "server_url"
        const val ACTION_STOP = "com.xiangqi.assist.STOP_CAPTURE"

        var onResult: ((ApiClient.AnalysisResult?) -> Unit)? = null
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopCapture()
                return START_NOT_STICKY
            }
            else -> {
                val resultCode = intent?.getIntExtra(EXTRA_RESULT_CODE, -1) ?: -1
                val data = intent?.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
                val serverUrl = intent?.getStringExtra(EXTRA_SERVER_URL) ?: ""

                if (resultCode != -1 && data != null) {
                    startForeground(1, createNotification("象棋辅助运行中..."))
                    startCapture(resultCode, data, serverUrl)
                }
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                "capture_channel", "截屏服务",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(text: String): Notification {
        return NotificationCompat.Builder(this, "capture_channel")
            .setContentTitle("象棋辅助")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()
    }

    private fun startCapture(resultCode: Int, data: Intent, serverUrl: String) {
        val metrics = DisplayMetrics().also {
            val wm = getSystemService(WINDOW_SERVICE) as WindowManager
            wm.defaultDisplay.getRealMetrics(it)
        }
        val density = metrics.densityDpi
        val width = metrics.widthPixels
        val height = metrics.heightPixels

        // 创建 MediaProjection
        val mpManager = getSystemService(MEDIA_PROJECTION_SERVICE) as
                android.media.projection.MediaProjectionManager
        mediaProjection = mpManager.getMediaProjection(resultCode, data)

        // 创建 ImageReader
        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)

        // 创建 VirtualDisplay
        virtualDisplay = mediaProjection.createVirtualDisplay(
            "capture_display",
            width, height, density,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader?.surface, null, null
        )

        val apiClient = ApiClient(serverUrl)

        // 定时截屏 (每 2 秒)
        captureJob = scope.launch {
            while (isActive) {
                captureAndAnalyze(apiClient, width, height)
                delay(2000)
            }
        }
    }

    private suspend fun captureAndAnalyze(apiClient: ApiClient, width: Int, height: Int) {
        val reader = imageReader ?: return

        val image = reader.acquireLatestImage() ?: return
        val planes = image.planes
        val buffer = planes[0].buffer
        val pixelStride = planes[0].pixelStride
        val rowStride = planes[0].rowStride
        val rowPadding = rowStride - pixelStride * width

        val bitmap = Bitmap.createBitmap(
            width + rowPadding / pixelStride, height,
            Bitmap.Config.ARGB_8888
        )
        bitmap.copyPixelsFromBuffer(buffer)
        image.close()

        // 裁剪到实际宽度
        val cropped = Bitmap.createBitmap(bitmap, 0, 0, width, height)

        // 分析
        val result = apiClient.analyze(cropped)
        onResult?.invoke(result)
    }

    private fun stopCapture() {
        captureJob?.cancel()
        virtualDisplay?.release()
        imageReader?.close()
        if (::mediaProjection.isInitialized) {
            mediaProjection.stop()
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }
}
