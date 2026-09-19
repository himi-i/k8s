pipeline {
  agent {
    kubernetes {
      // jnlp(agent) 컨테이너는 플러그인이 자동으로 추가함. git/sed 는 jnlp 이미지에 이미 포함.
      yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
  - name: kaniko
    image: gcr.io/kaniko-project/executor:v1.24.0-debug
    command: ["/busybox/cat"]
    tty: true
    resources:
      requests: { cpu: 500m, memory: 1Gi }
      limits:   { cpu: "2",  memory: 3Gi }   # torch 레이어 빌드 시 OOMKilled 나면 조정
    volumeMounts:
    - name: docker-config
      mountPath: /kaniko/.docker
  volumes:
  - name: docker-config
    secret:
      secretName: dockerhub-regcred
      items:
      - key: .dockerconfigjson
        path: config.json
'''
    }
  }

  options {
    timeout(time: 40, unit: 'MINUTES')
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    IMAGE         = 'ikdamservice/k8s-project'
    MANIFEST_REPO = 'github.com/himi-i/k8s-manifests.git'
    MANIFEST_PATH = 'apps/ai-inference/01-deployment.yaml'
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          env.IMAGE_TAG = env.GIT_COMMIT.take(7)
        }
      }
    }

    stage('Build & Push (Kaniko)') {
      steps {
        container('kaniko') {
          sh '''
            /kaniko/executor \
              --context "$(pwd)" \
              --dockerfile "$(pwd)/Dockerfile" \
              --destination "${IMAGE}:${IMAGE_TAG}" \
              --destination "${IMAGE}:latest" \
              --snapshot-mode=redo \
              --use-new-run
          '''
        }
      }
    }

    stage('Update manifest repo') {
      steps {
        withCredentials([usernamePassword(
          credentialsId: 'github-pat',
          usernameVariable: 'GH_USER',
          passwordVariable: 'GH_TOKEN')]) {
          sh '''
            rm -rf manifests
            git clone --depth 1 "https://${GH_USER}:${GH_TOKEN}@${MANIFEST_REPO}" manifests
            cd manifests

            git config user.name  "jenkins-bot"
            git config user.email "jenkins-bot@users.noreply.github.com"

            sed -i "s|image: ${IMAGE}:.*|image: ${IMAGE}:${IMAGE_TAG}|" "${MANIFEST_PATH}"

            if git diff --quiet; then
              echo "manifest unchanged, nothing to push"
              exit 0
            fi

            git commit -am "ci(ai-inference): ${IMAGE}:${IMAGE_TAG}"
            git push origin HEAD:main
          '''
        }
      }
    }
  }
}
