package com.xiangqi.assist

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.os.Build
import android.os.IBinder
import android.view.*
import android.widget.*
import kotlinx.coroutines.*

/**
 * 悬浮窗服务 — 在所有应用上方显示走法建议
 *
 * 需要 SYSTEM_ALERT_WINDOW 权限
 */
class OverlayService : Service() {

    private lateinit var windowManager: WindowManager
    private var overlayView: View? = null
    private var moveText: TextView? = null
    private var scoreText: TextView? = null
    private var isCollapsed = false

    private var lastResult: ApiClient.AnalysisResult? = null

    companion object {
        const val ACTION_UPDATE = "com.xiangqi.assist.UPDATE_RESULT"
        const val EXTRA_RESULT = "result"

        var isRunning = false
    }

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        createOverlay()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_UPDATE) {
            val result = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                intent.getSerializableExtra(EXTRA_RESULT, ApiClient.AnalysisResult::class.java)
            } else {
                @Suppress("DEPRECATION")
                intent.getSerializableExtra(EXTRA_RESULT) as? ApiClient.AnalysisResult
            }
            if (result != null) {
                lastResult = result
                updateDisplay(result)
            }
            return START_STICKY
        }

        if (!isRunning) {
            createOverlay()
            isRunning = true
        }
        return START_STICKY
    }

    private fun createOverlay() {
        if (overlayView != null) return

        // 悬浮窗布局
        val inflater = getSystemService(LAYOUT_INFLATER_SERVICE) as LayoutInflater
        overlayView = inflater.inflate(R.layout.overlay_layout, null)

        moveText = overlayView?.findViewById(R.id.overlay_move)
        scoreText = overlayView?.findViewById(R.id.overlay_score)

        // 关闭按钮
        overlayView?.findViewById<ImageButton>(R.id.overlay_close)?.setOnClickListener {
            stopSelf()
        }

        // 展开/折叠 (点击切换)
        overlayView?.setOnClickListener {
            toggleCollapse()
        }

        // 窗口参数
        val layoutFlag = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            WindowManager.LayoutParams.TYPE_SYSTEM_ALERT
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            layoutFlag,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                    WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        )

        params.gravity = Gravity.TOP or Gravity.END
        params.x = 0
        params.y = 100

        try {
            windowManager.addView(overlayView, params)
            updateDisplay(lastResult)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun updateDisplay(result: ApiClient.AnalysisResult?) {
        if (overlayView == null) return
        moveText?.text = result?.bestMove ?: "--"
        scoreText?.text = if (result != null) "评分: ${result.score}" else ""
    }

    private fun toggleCollapse() {
        isCollapsed = !isCollapsed
        moveText?.visibility = if (isCollapsed) View.GONE else View.VISIBLE
        scoreText?.visibility = if (isCollapsed) View.GONE else View.VISIBLE
        // 折叠时只显示走法
        if (isCollapsed) {
            moveText?.visibility = View.VISIBLE
            moveText?.textSize = 16f
        } else {
            moveText?.textSize = 28f
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        overlayView?.let { view ->
            try {
                windowManager.removeView(view)
            } catch (e: Exception) {
                // 视图可能已被移除
            }
        }
        overlayView = null
    }
}
