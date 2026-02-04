pipeline {
    agent any
    options {
        disableConcurrentBuilds(abortPrevious: true)
    }
    environment {
        REPO_NAME = "${env.JOB_NAME}".replaceAll("/${env.BRANCH_NAME}", '')
    }
    stages {
        stage('Deploy') {
            when {
                branch 'production'
            }
            steps {
                script {
                    sh '''
                        echo "Copying .env files from /src/${REPO_NAME}..."
                        cp /src/${REPO_NAME}/*.env . || echo "No .env files found"
                        echo "Building and starting production containers..."
                        docker compose -f docker-compose.prod.yml -p fourmizzz_auto_tracker_v2 up -d --build
                    '''
                }
            }
        }
    }
    post {
        always {
            script {
                sh '''
                    echo "Cleaning up dangling Docker images..."
                    docker system prune -af
                '''
            }
        }
    }
}
