import Login from '../components/auth/Login'

const LoginPage = () => {
  return (
<div className="container-fluid vh-100 bg-light px-0 d-flex justify-content-center align-items-center flex-column flex-lg-row">
  <div className="col-lg-4 col-sm-12 text-center text-lg-start">
    <div className="col-12 d-flex justify-content-center align-items-center">
      <div className="col-lg-10 col-sm-12">
        <p className="display-1 fw-bold text-secondary">
          <span className="text-danger">Prima</span>dmin.
        </p>
      </div>
    </div>
  </div>

  <div className="col-lg-5 col-sm-12 d-flex justify-content-center align-items-center px-5 border-start border-dark">
    <Login />
  </div>
</div>


  )
}

export default LoginPage